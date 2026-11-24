<template>
	<div data-testid="sellos-visits-page">
		<PageHeader title="Site visits" :text="scopeNote" icon="lucide-calendar-check" />
		<LoadError
			v-if="error"
			class="mb-ui-md"
			data-testid="sellos-visits-error"
			:message="error"
			@retry="retry"
		/>

		<div
			class="mb-ui-md grid grid-cols-2 gap-ui-md md:grid-cols-4"
			data-testid="sellos-visits-stats"
		>
			<StatCard
				label="Tomorrow to confirm"
				:value="tomorrow ? tomorrow.visits.length : 0"
				icon="lucide-calendar-clock"
				tone="warning"
			/>
			<StatCard label="In this view" :value="inView" icon="lucide-calendar-days" />
		</div>

		<ListCard title="Tomorrow's visits to confirm" class="mb-ui-md">
			<p class="mb-ui-sm text-sm text-ink-muted" data-testid="sellos-visits-tomorrow-date">
				{{ tomorrow ? dayLabel(tomorrow.date) : "" }}
			</p>
			<EmptyState
				v-if="tomorrow && !tomorrow.visits.length"
				title="No visits tomorrow."
				text="Visits booked for tomorrow will be listed here to confirm."
				icon="lucide-calendar-x"
				data-testid="sellos-visits-tomorrow-empty"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-visits-tomorrow">
				<li
					v-for="v in tomorrow?.visits || []"
					:key="v.name"
					data-testid="sellos-visits-tomorrow-item"
					class="rounded-card border border-line-soft bg-surface-faint p-ui-md"
				>
					<div class="flex flex-wrap items-center justify-between gap-ui-sm">
						<span class="text-ink">
							<router-link :to="`/crm/leads/${v.lead}`" class="ui-link">{{
								v.lead_title
							}}</router-link>
							, {{ v.project_name }} at {{ timeOf(v.visit_datetime) }}
							<span class="text-sm text-ink-muted">, {{ v.agent_name }}</span>
						</span>
						<StatusBadge
							data-testid="sellos-visits-tomorrow-status"
							:tone="confirmTone(v.confirmation_status)"
							:label="v.confirmation_status"
						/>
					</div>
					<VisitConfirm
						class="mt-ui-sm"
						:visit="v"
						:confirmations="options.confirmations"
						@changed="loadAll"
					/>
				</li>
			</ul>
		</ListCard>

		<ListCard title="Calendar">
			<div class="mb-ui-sm flex flex-wrap items-center justify-between gap-ui-sm">
				<p class="text-sm text-ink-muted" data-testid="sellos-visits-range">
					{{ calendar ? rangeLabel : "" }}
				</p>
				<div class="flex flex-wrap gap-ui-sm">
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
			</div>
			<LoadingSkeleton v-if="!calendar && !error" :rows="3" />
			<ul class="space-y-ui-sm" data-testid="sellos-visits-calendar">
				<li
					v-for="d in calendar?.days || []"
					:key="d.date"
					data-testid="sellos-visits-day"
					:data-date="d.date"
					class="rounded-card border border-line-soft bg-surface-faint p-ui-md"
				>
					<p class="text-sm font-medium text-ink">{{ dayLabel(d.date) }}</p>
					<p v-if="!d.visits.length" class="text-sm text-ink-muted">No visits.</p>
					<ul class="space-y-1">
						<li
							v-for="v in d.visits"
							:key="v.name"
							data-testid="sellos-visits-item"
							class="flex flex-wrap items-center gap-ui-sm text-sm text-ink"
						>
							<span>
								{{ timeOf(v.visit_datetime) }}
								<router-link :to="`/crm/leads/${v.lead}`" class="ui-link">{{
									v.lead_title
								}}</router-link>
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
		</ListCard>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import StatCard from "../components/StatCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import VisitConfirm from "../components/VisitConfirm.vue";
import { crmApi, serverMessage } from "../crm/crmApi";
import { session } from "../session";

// SOS-P1-25: the calendar of visits by day and week, and tomorrow's visits to confirm. The server
// decides whose visits are listed: an Agent's own, a Sales Manager's team's, a Company Admin's everyone's.
const view = ref("week");
const date = ref(null); // a day of the window shown. null is today.
const calendar = ref(null);
const tomorrow = ref(null);
const options = ref({ confirmations: [] });
const error = ref("");

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

const inView = computed(() =>
	(calendar.value?.days || []).reduce((total, day) => total + day.visits.length, 0)
);

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

function dayLabel(value) {
	const day = new Date(`${String(value).slice(0, 10)}T00:00:00`);
	return day.toLocaleDateString("en-IN", {
		weekday: "short",
		day: "numeric",
		month: "short",
		year: "numeric",
	});
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
