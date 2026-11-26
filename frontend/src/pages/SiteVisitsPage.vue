<template>
	<PageTemplate shape="list" data-testid="sellos-visits-page">
		<template #header>
			<PageHeader title="Site visits" :text="scopeNote" icon="lucide-calendar-check">
				<div class="flex flex-wrap gap-ui-sm" role="group" aria-label="Calendar view">
					<AppButton
						v-for="v in ['day', 'week']"
						:key="v"
						type="button"
						:active="view === v"
						:aria-pressed="view === v"
						:data-testid="`sellos-visits-view-${v}`"
						@click="setView(v)"
					>
						{{ v === "day" ? "Day" : "Week" }}
					</AppButton>
				</div>
				<div class="flex flex-wrap gap-ui-sm" role="group" aria-label="Move the calendar">
					<AppButton type="button" data-testid="sellos-visits-prev" @click="step(-1)">
						Previous
					</AppButton>
					<AppButton type="button" data-testid="sellos-visits-today" @click="goToday">
						Today
					</AppButton>
					<AppButton type="button" data-testid="sellos-visits-next" @click="step(1)">
						Next
					</AppButton>
				</div>
			</PageHeader>
		</template>

		<template #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-visits-stats" />
		</template>

		<template #filters>
			<FilterBar
				v-model:search="search"
				search-label="Search site visits"
				search-placeholder="Search by lead, project or agent"
				search-testid="sellos-visits-search"
				clear-testid="sellos-visits-filter-clear"
				:active="Boolean(search || statusFilter || projectFilter)"
				:chips="chips"
				data-testid="sellos-visits-filters"
				@clear="clearFilters"
				@remove-chip="removeChip"
			>
				<FormField
					v-model="statusFilter"
					compact
					type="select"
					label="Status"
					:options="statusOptions"
					data-testid="sellos-visits-filter-status"
				/>
				<FormField
					v-model="projectFilter"
					compact
					type="select"
					label="Project"
					:options="projectOptions"
					data-testid="sellos-visits-filter-project"
				/>
			</FilterBar>
		</template>

		<LoadError
			v-if="error"
			class="mb-ui-md"
			data-testid="sellos-visits-error"
			:message="error"
			@retry="retry"
		/>

		<p class="mb-ui-sm ui-text-muted" data-testid="sellos-visits-tomorrow-date">
			{{ tomorrow ? dayLabel(tomorrow.date) : "" }}
		</p>
		<DataTable
			class="mb-ui-md"
			title="Tomorrow's visits to confirm"
			caption="Tomorrow's visits to confirm"
			:columns="tomorrowColumns"
			dense
			:rows="tomorrowShown"
			:loading="!tomorrow && !error"
			loading-label="Loading tomorrow's visits."
			:row-name="(v) => v.lead_title"
			empty-title="No visits tomorrow."
			empty-text="Visits booked for tomorrow will be listed here to confirm."
			empty-icon="lucide-calendar-x"
			testid="sellos-visits-tomorrow"
			row-testid="sellos-visits-tomorrow-item"
			empty-testid="sellos-visits-tomorrow-empty"
		>
			<template #cell-lead_title="{ row }">
				<router-link :to="`/crm/leads/${row.lead}`" class="ui-link ui-text-strong">{{
					row.lead_name || row.lead_title
				}}</router-link>
				<span v-if="row.lead_source" class="block ui-text-muted">{{
					row.lead_source
				}}</span>
			</template>
			<template #cell-visit_datetime="{ row }">{{
				formatDateTime(row.visit_datetime)
			}}</template>
			<template #cell-confirmation_status="{ row }">
				<StatusBadge
					data-testid="sellos-visits-tomorrow-status"
					:tone="confirmTone(row.confirmation_status)"
					:label="row.confirmation_status"
				/>
			</template>
			<template #cell-confirm="{ row }">
				<VisitConfirm
					compact
					:visit="row"
					:confirmations="options.confirmations"
					@changed="loadAll"
				/>
			</template>
		</DataTable>

		<SectionCard title="Calendar">
			<p class="mb-ui-sm ui-text-muted" data-testid="sellos-visits-range">
				{{ calendar ? rangeLabel : "" }}
			</p>
			<LoadingSkeleton v-if="!calendar && !error" :rows="3" />
			<ul class="space-y-ui-md" data-testid="sellos-visits-calendar">
				<li
					v-for="d in shownDays"
					:key="d.date"
					data-testid="sellos-visits-day"
					:data-date="d.date"
					class="space-y-1"
				>
					<p class="ui-text-strong">{{ dayLabel(d.date) }}</p>
					<p v-if="!d.visits.length" class="ui-text-muted">No visits.</p>
					<ul class="space-y-1">
						<li
							v-for="v in d.visits"
							:key="v.name"
							data-testid="sellos-visits-item"
							class="flex flex-wrap items-center gap-ui-sm ui-text-small"
						>
							<span>
								{{ timeOf(v.visit_datetime) }}
								<router-link :to="`/crm/leads/${v.lead}`" class="ui-link">{{
									v.lead_name || v.lead_title
								}}</router-link>
								<span v-if="v.lead_source" class="ui-text-muted">{{
									v.lead_source
								}}</span>
								, {{ v.project_name }}, {{ v.agent_name }}
							</span>
							<StatusBadge
								:tone="visitTone(v)"
								:label="
									v.status === 'Scheduled' ? v.confirmation_status : v.status
								"
							/>
						</li>
					</ul>
				</li>
			</ul>
		</SectionCard>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import FilterBar from "../components/FilterBar.vue";
import FormField from "../components/FormField.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import SectionCard from "../components/SectionCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import VisitConfirm from "../components/VisitConfirm.vue";
import { crmApi, serverMessage } from "../crm/crmApi";
import { formatDate, formatDateTime } from "../format";
import { session } from "../session";

// SOS-P1-25: the calendar of visits by day and week, and tomorrow's visits to confirm. The server
// decides whose visits are listed: an Agent's own, a Sales Manager's team's, a Company Admin's everyone's.
const view = ref("week");
const date = ref(null); // a day of the window shown. null is today.
const calendar = ref(null);
const tomorrow = ref(null);
const options = ref({ confirmations: [] });
const error = ref("");

const tomorrowColumns = [
	{ key: "lead_title", label: "Lead", primary: true },
	{ key: "project_name", label: "Project" },
	{ key: "visit_datetime", label: "When" },
	{ key: "agent_name", label: "Agent" },
	{ key: "confirmation_status", label: "Status" },
	{ key: "confirm", label: "Confirm", wrap: true },
];

const scopeNote = computed(() => {
	if (session.roles.includes("SellOS Company Admin")) return "Everyone's site visits.";
	if (session.roles.includes("SellOS Sales Manager")) return "Your team's site visits.";
	return "Your site visits.";
});
const rangeLabel = computed(() =>
	calendar.value.start === calendar.value.end
		? dayLabel(calendar.value.start)
		: `${dayLabel(calendar.value.start)} to ${dayLabel(calendar.value.end)}`
);

// The filters apply to tomorrow's table and to the calendar alike.
const search = ref("");
const statusFilter = ref("");
const projectFilter = ref("");
const stateOf = (v) => (v.status === "Scheduled" ? v.confirmation_status : v.status);
const allVisits = computed(() => [
	...(tomorrow.value?.visits || []),
	...(calendar.value?.days || []).flatMap((d) => d.visits),
]);
const choose = (label, values) => [
	{ label, value: "" },
	...[...new Set(values.filter(Boolean))].sort().map((v) => ({ label: v, value: v })),
];
const statusOptions = computed(() => choose("Any status", allVisits.value.map(stateOf)));
const projectOptions = computed(() =>
	choose(
		"Any project",
		allVisits.value.map((v) => v.project_name)
	)
);
const matches = (v) => {
	const q = search.value.trim().toLowerCase();
	return (
		(!q ||
			`${v.lead_name || ""} ${v.lead_title || ""} ${v.project_name || ""} ${
				v.agent_name || ""
			}`
				.toLowerCase()
				.includes(q)) &&
		(!statusFilter.value || stateOf(v) === statusFilter.value) &&
		(!projectFilter.value || v.project_name === projectFilter.value)
	);
};
const tomorrowShown = computed(() => (tomorrow.value?.visits || []).filter(matches));
const shownDays = computed(() =>
	(calendar.value?.days || []).map((d) => ({ ...d, visits: d.visits.filter(matches) }))
);
const chips = computed(() => [
	...(search.value ? [{ key: "search", label: `Search: ${search.value}` }] : []),
	...(statusFilter.value ? [{ key: "status", label: `Status: ${statusFilter.value}` }] : []),
	...(projectFilter.value ? [{ key: "project", label: `Project: ${projectFilter.value}` }] : []),
]);
function clearFilters() {
	search.value = statusFilter.value = projectFilter.value = "";
}
function removeChip(key) {
	const refs = { search, status: statusFilter, project: projectFilter };
	refs[key].value = "";
}
const inView = computed(() =>
	shownDays.value.reduce((total, day) => total + day.visits.length, 0)
);
const kpis = computed(() => [
	{
		label: "Tomorrow to confirm",
		value: tomorrow.value ? tomorrow.value.visits.length : 0,
		caption: "Visits waiting for a call",
		icon: "lucide-calendar-clock",
		tone: "warning",
	},
	{
		label: "In this view",
		value: inView.value,
		caption: view.value === "day" ? "On the day shown" : "In the week shown",
		icon: "lucide-calendar-days",
	},
]);

// Status is a word and an icon in a tone, never colour alone.
function confirmTone(status) {
	if (status === "Confirmed") return "success";
	if (status === "Cancelled") return "danger";
	if (status === "Rescheduled") return "info";
	return "warning";
}

function visitTone(visit) {
	if (visit.status === "Done") return "success";
	if (visit.status === "Scheduled") return confirmTone(visit.confirmation_status);
	return "neutral";
}

// "Tue, 24 Nov 2026": the weekday from the date, the rest in the shared date format.
function dayLabel(value) {
	const day = new Date(`${String(value).slice(0, 10)}T00:00:00`);
	const weekday = day.toLocaleDateString("en-IN", { weekday: "short" });
	return `${weekday}, ${formatDate(String(value).slice(0, 10))}`;
}

function timeOf(value) {
	return String(value).slice(11, 16);
}

function shift(day, days) {
	const next = new Date(`${day}T00:00:00`);
	next.setDate(next.getDate() + days);
	const pad = (n) => String(n).padStart(2, "0");
	return `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}`;
}

// Only the newest request may fill the screen: a slower, older answer (the week the page opened
// with) must not overwrite the day the user has since chosen.
let latestLoad = 0;

async function loadAll() {
	const mine = ++latestLoad;
	error.value = "";
	try {
		const [cal, tom] = await Promise.all([
			crmApi.siteVisitCalendar(view.value, date.value),
			crmApi.tomorrowsSiteVisits(),
		]);
		if (mine !== latestLoad) return;
		calendar.value = cal;
		tomorrow.value = tom;
	} catch (e) {
		if (mine !== latestLoad) return;
		error.value = serverMessage(e, "The site visits could not be loaded.");
	}
}

function setView(next) {
	view.value = next;
	loadAll();
}

function step(direction) {
	const first = calendar.value.start;
	date.value = shift(first, direction * (view.value === "week" ? 7 : 1));
	loadAll();
}

function goToday() {
	date.value = null;
	loadAll();
}

async function loadOptions() {
	try {
		options.value = await crmApi.siteVisitOptions();
	} catch (e) {
		error.value = serverMessage(e, "The site visit lists could not be loaded.");
	}
}

async function retry() {
	await loadOptions();
	await loadAll();
}

onMounted(retry);
</script>
