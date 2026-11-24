<template>
	<PageTemplate data-testid="sellos-leads-page" :data-view="view">
		<template #header>
			<PageHeader
				title="Leads"
				text="Everyone who has asked about a property, and where each enquiry stands."
				icon="lucide-users"
			>
				<div class="flex gap-ui-sm" role="group" aria-label="View">
					<AppButton
						type="button"
						:aria-pressed="view === 'list'"
						:active="view === 'list'"
						data-testid="sellos-leads-view-list"
						@click="setView('list')"
					>
						List
					</AppButton>
					<AppButton
						type="button"
						:aria-pressed="view === 'board'"
						:active="view === 'board'"
						data-testid="sellos-leads-view-board"
						@click="setView('board')"
					>
						Board
					</AppButton>
				</div>
				<AppButton
					v-if="canCreate"
					type="button"
					variant="primary"
					data-testid="sellos-leads-new"
					@click="creating = true"
				>
					<template #prefix
						><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
					/></template>
					New lead
				</AppButton>
			</PageHeader>
		</template>

		<template v-if="view === 'list' && !loadError" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-leads-stats" />
		</template>

		<template #filters>
			<FilterBar
				v-model:search="search"
				v-model:open="moreOpen"
				search-label="Search leads"
				search-placeholder="Search by name, source or campaign"
				search-testid="sellos-leads-search"
				more-testid="sellos-leads-filters-toggle"
				clear-testid="sellos-leads-filter-clear"
				apply-testid="sellos-leads-filter-apply"
				:more-count="moreActive"
				:active="filtersOn"
				data-testid="sellos-leads-filters"
				@update:search="load"
				@apply="load"
				@clear="clearFilters"
			>
				<FormField
					compact
					:model-value="filters.stage"
					type="select"
					label="Stage"
					:options="
						withAny(
							'Any stage',
							stages.map((st) => st.name)
						)
					"
					data-testid="sellos-leads-filter-stage"
					@update:model-value="setFilter('stage', $event)"
				/>
				<FormField
					compact
					:model-value="filters.assigned_to"
					type="select"
					label="Agent"
					:options="
						withAny(
							'Any agent',
							options.agents.map((a) => ({ value: a.name, label: a.full_name }))
						)
					"
					data-testid="sellos-leads-filter-agent"
					@update:model-value="setFilter('assigned_to', $event)"
				/>
				<FormField
					compact
					:model-value="filters.source"
					type="select"
					label="Source"
					:options="
						withAny(
							'Any source',
							filterSources.map((so) => so.name)
						)
					"
					data-testid="sellos-leads-filter-source"
					@update:model-value="setFilter('source', $event)"
				/>
				<template #more>
					<MoneyField
						v-model="filters.budget_min"
						label="Budget from (Rs)"
						data-testid="sellos-leads-filter-budget-min"
					/>
					<MoneyField
						v-model="filters.budget_max"
						label="Budget to (Rs)"
						data-testid="sellos-leads-filter-budget-max"
					/>
					<FormField
						v-model="filters.configuration"
						type="select"
						label="Configuration"
						:options="withAny('Any configuration', CONFIGURATIONS)"
						data-testid="sellos-leads-filter-configuration"
					/>
					<FormField
						v-model="filters.locality"
						label="Locality"
						data-testid="sellos-leads-filter-locality"
					/>
					<FormField
						v-model="filters.timeline"
						type="select"
						label="Timeline"
						:options="withAny('Any timeline', TIMELINES)"
						data-testid="sellos-leads-filter-timeline"
					/>
					<FormField
						v-if="options.teams.length"
						:model-value="filters.team"
						type="select"
						label="Team"
						:options="
							withAny(
								'Any team',
								options.teams.map((t) => ({ value: t.name, label: t.team_name }))
							)
						"
						data-testid="sellos-leads-filter-team"
						@update:model-value="setFilter('team', $event)"
					/>
					<FormField
						:model-value="filters.consent_status"
						type="select"
						label="Consent status"
						:options="withAny('Any consent status', options.consent_statuses)"
						data-testid="sellos-leads-filter-consent"
						@update:model-value="setFilter('consent_status', $event)"
					/>
					<FormField
						:model-value="filters.last_contacted_from"
						type="date"
						label="Last contacted from"
						data-testid="sellos-leads-filter-contacted-from"
						@update:model-value="setFilter('last_contacted_from', $event)"
					/>
					<FormField
						:model-value="filters.last_contacted_to"
						type="date"
						label="Last contacted to"
						data-testid="sellos-leads-filter-contacted-to"
						@update:model-value="setFilter('last_contacted_to', $event)"
					/>
					<FormField
						:model-value="filters.follow_up"
						type="select"
						label="Follow up"
						:options="followUpOptions"
						data-testid="sellos-leads-filter-follow-up"
						@update:model-value="setFilter('follow_up', $event)"
					/>
					<FormField
						:model-value="filters.sort"
						type="select"
						label="Sort"
						:options="sortOptions"
						data-testid="sellos-leads-sort"
						@update:model-value="setFilter('sort', $event)"
					/>
					<FormField
						:model-value="untouchedOnly"
						type="checkbox"
						:label="`No activity for ${untouchedDays} days`"
						data-testid="sellos-leads-filter-untouched"
						@update:model-value="
							(v) => {
								untouchedOnly = v;
								load();
							}
						"
					/>
				</template>
			</FilterBar>
		</template>

		<!-- The new lead form is a drawer: nothing is an open form under the list. -->
		<FormDrawer
			v-if="canCreate"
			:open="creating"
			title="New lead"
			text="A person who has asked about a property."
			submit-label="Save lead"
			testid="sellos-lead-form"
			submit-testid="sellos-lead-form-save"
			@close="creating = false"
			@submit="create(false)"
		>
			<FormSection title="Client">
				<FormField
					v-model="form.client_name"
					label="Client name"
					required
					data-testid="sellos-lead-form-name"
				/>
				<FormField
					v-model="form.client_type"
					type="select"
					label="Client type"
					:options="CLIENT_TYPES"
					data-testid="sellos-lead-form-type"
				/>
				<FormField
					v-model="form.phone"
					label="Phone"
					data-testid="sellos-lead-form-phone"
				/>
				<FormField
					v-model="form.email"
					type="email"
					label="Email"
					data-testid="sellos-lead-form-email"
				/>
				<FormField
					v-if="form.client_type === 'NRI'"
					v-model="form.overseas_phone"
					label="Overseas phone (optional)"
				/>
				<FormField
					v-if="form.client_type === 'NRI'"
					v-model="form.country_of_residence"
					label="Country of residence (optional)"
				/>
			</FormSection>
			<FormSection title="Enquiry">
				<FormField
					v-model="form.source"
					type="select"
					label="Source"
					required
					:options="sourceOptions"
					data-testid="sellos-lead-form-source"
				/>
				<FormField
					v-model="form.campaign"
					label="Campaign (optional)"
					data-testid="sellos-lead-form-campaign"
				/>
				<div
					v-if="canManageSources"
					class="flex items-end gap-ui-sm md:col-span-2"
					data-testid="sellos-lead-source-add"
				>
					<FormField
						v-model="newSource"
						label="Add a source to the list"
						class="flex-1"
						data-testid="sellos-lead-source-new"
						@keydown.enter.prevent="addSource"
					/>
					<AppButton
						type="button"
						data-testid="sellos-lead-source-add-button"
						@click="addSource"
					>
						Add source
					</AppButton>
				</div>
			</FormSection>
			<section
				v-if="duplicates.length"
				role="alert"
				data-testid="sellos-duplicate-warning"
				class="space-y-ui-md rounded border border-tone-warning-line bg-tone-warning-bg p-ui-md text-sm text-tone-warning"
			>
				<p class="font-medium">
					This person is already in SellOS. Add the enquiry to them instead of making a
					second client.
				</p>
				<div
					v-for="match in duplicates"
					:key="match.name"
					data-testid="sellos-duplicate-match"
					:data-visible="match.visible ? 'yes' : 'no'"
					class="rounded border border-line bg-surface p-ui-md text-ink"
				>
					<p data-testid="sellos-duplicate-name" class="font-medium">
						{{ match.visible ? match.client_name : "A client of another agent" }}
					</p>
					<p class="text-ink-muted">
						Same {{ match.matched_on.map(matchLabel).join(" and ") }}.
						<span data-testid="sellos-duplicate-phone">{{ match.phone }}</span>
					</p>
					<ul v-if="match.leads.length" class="mt-1">
						<li
							v-for="lead in match.leads"
							:key="lead.name"
							data-testid="sellos-duplicate-lead"
						>
							{{ lead.lead_title }}
						</li>
					</ul>
					<p v-if="!match.can_add" class="mt-1 text-ink-muted">
						You cannot see this client. Ask a Company Admin to look at it.
					</p>
					<AppButton
						v-else
						type="button"
						class="mt-ui-sm"
						data-testid="sellos-duplicate-add"
						@click="addToExisting(match)"
					>
						Add this enquiry to {{ match.client_name }}
					</AppButton>
				</div>
				<AppButton type="button" data-testid="sellos-duplicate-new" @click="create(true)">
					Save as a new client anyway
				</AppButton>
			</section>
			<p v-if="error" data-testid="sellos-lead-form-error" class="text-sm text-danger">
				{{ error }}
			</p>
		</FormDrawer>

		<LoadError
			v-if="loadError"
			:message="loadError"
			class="mb-ui-md"
			data-testid="sellos-leads-error"
			@retry="load"
		/>
		<LeadBoard
			v-if="view === 'board' && !loadError"
			:columns="board.columns"
			:can-move="!partner"
			:base-path="basePath"
			:untouched-days="untouchedDays"
			@moved="load"
		/>

		<!-- The result of the last bulk move. It stays after the selection is gone. -->
		<p
			v-if="bulkNotice"
			role="status"
			class="mb-ui-md text-sm text-ink"
			data-testid="sellos-bulk-result"
		>
			{{ bulkNotice }}
		</p>
		<p
			v-if="bulkError"
			role="alert"
			class="mb-ui-md text-sm text-danger"
			data-testid="sellos-bulk-error"
		>
			{{ bulkError }}
		</p>
		<!-- The bulk bar exists only while rows are selected. -->
		<BulkBar v-if="canReassign" :count="selected.length" @clear="selected = []">
			<form class="flex flex-wrap items-end gap-ui-md" @submit.prevent="bulkReassign">
				<FormField
					v-model="bulkAgent"
					type="select"
					label="Give the selected leads to"
					required
					:options="reassignAgents.map((a) => ({ value: a.name, label: a.full_name }))"
					class="min-w-[14rem]"
					data-testid="sellos-bulk-agent"
				/>
				<AppButton
					type="submit"
					variant="primary"
					:disabled="!selected.length"
					data-testid="sellos-bulk-reassign"
				>
					Reassign selected
				</AppButton>
			</form>
		</BulkBar>

		<DataTable
			v-if="view === 'list' && !loadError"
			v-model:selected="selected"
			title="All leads"
			caption="Leads"
			:columns="columns"
			:rows="leads"
			:loading="loading"
			loading-label="Loading leads."
			:selectable="canReassign"
			:row-to="rowTo"
			:row-name="(row) => row.client_name"
			:actions="rowActions"
			empty-title="No leads yet"
			empty-text="Leads you may see will be listed here. Try clearing the filters, or add a lead."
			empty-icon="lucide-users"
			testid="sellos-leads-list"
			row-testid="sellos-lead-row"
			select-testid="sellos-lead-select"
			select-all-testid="sellos-bulk-select-all"
			loading-testid="sellos-leads-loading"
			empty-testid="sellos-leads-empty"
		>
			<template #cell-client_name="{ row }">
				<span class="block">{{ row.client_name }}</span>
				<span v-if="row.phone" class="block text-sm font-normal text-ink-muted">{{
					row.phone
				}}</span>
			</template>
			<template #cell-project="{ row }">
				<span class="text-ink-body">{{ projectInterest(row) }}</span>
			</template>
			<template #cell-source="{ row }">
				<span class="text-ink-body" data-testid="sellos-lead-source">{{
					row.campaign ? `${row.source} · ${row.campaign}` : row.source
				}}</span>
			</template>
			<template #cell-stage="{ row }">
				<StatusBadge
					v-if="row.stage"
					:label="row.stage"
					tone="neutral"
					data-testid="sellos-lead-row-stage"
				/>
			</template>
			<template #cell-assigned_to="{ row }">
				<span class="text-ink-body">{{ agentName(row.assigned_to) }}</span>
			</template>
			<template #cell-budget="{ row }">
				<span class="tabular-nums">{{ formatMoney(row.budget || "") }}</span>
			</template>
			<template #cell-consent_status="{ row }">
				<StatusBadge
					v-if="row.consent_status"
					:label="row.consent_status"
					:tone="consentTone(row)"
					data-testid="sellos-lead-row-consent"
				/>
			</template>
			<template #cell-last_contacted="{ row }">
				<span class="text-ink-body">{{
					row.last_contacted ? formatWhen(row.last_contacted) : "Never"
				}}</span>
			</template>
			<template #cell-next_follow_up="{ row }">
				<span
					v-if="row.next_follow_up"
					class="text-ink-body"
					data-testid="sellos-lead-next-follow-up"
					:data-state="row.follow_up_state"
				>
					{{ formatWhen(row.next_follow_up) }}
				</span>
			</template>
			<template #cell-flags="{ row }">
				<span class="flex flex-wrap items-center gap-ui-sm">
					<StatusBadge
						v-if="row.untouched"
						tone="warning"
						data-testid="sellos-untouched"
					>
						No activity for {{ untouchedDays }} days
					</StatusBadge>
					<StatusBadge
						v-if="row.follow_up_state === 'overdue'"
						tone="danger"
						data-testid="sellos-follow-up-overdue"
					>
						Follow up overdue
					</StatusBadge>
					<StatusBadge
						v-if="row.follow_up_untouched"
						tone="warning"
						data-testid="sellos-follow-up-untouched"
					>
						Untouched, no follow up for {{ followUpDays }} days
					</StatusBadge>
					<StatusBadge
						v-if="row.overdue_tasks"
						tone="danger"
						data-testid="sellos-lead-overdue"
					>
						{{ row.overdue_tasks }} overdue
					</StatusBadge>
				</span>
			</template>
		</DataTable>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { CLIENT_TYPES, CONFIGURATIONS, TIMELINES, crmApi, serverMessage } from "../crm/crmApi";
import { logBackgroundError } from "../api";
import AppButton from "../components/AppButton.vue";
import BulkBar from "../components/BulkBar.vue";
import DataTable from "../components/DataTable.vue";
import FilterBar from "../components/FilterBar.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LeadBoard from "../components/LeadBoard.vue";
import LoadError from "../components/LoadError.vue";
import MoneyField from "../components/MoneyField.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { formatMoney, formatWhen } from "../format";
import { session } from "../session";
import { shell } from "../shell";

const route = useRoute();
const router = useRouter();
const partner = computed(() => route.meta.area === "partner");
const basePath = computed(() => (partner.value ? "/partner/leads" : "/crm/leads"));
const canCreate = computed(() => !partner.value); // a channel partner logs nothing (CLAUDE.md)
const leads = ref([]);
const search = ref("");
const creating = ref(false);
const error = ref("");
const loadError = ref("");
const loading = ref(true);
const emptyFilters = () => ({
	budget_min: "",
	budget_max: "",
	configuration: "",
	locality: "",
	timeline: "",
	stage: "",
	assigned_to: "",
	team: "",
	source: "",
	consent_status: "",
	last_contacted_from: "",
	last_contacted_to: "",
	follow_up: "",
	sort: "",
});
const filters = reactive(emptyFilters());
const untouchedOnly = ref(false);
const untouchedDays = ref(7);
const followUpDays = ref(3);
const stages = ref([]);
const options = reactive({ agents: [], teams: [], consent_statuses: [] });
const filterSources = ref([]);
const board = reactive({ columns: [] });
const view = ref("list");
// One row of filters by default (search, stage, agent, source); the rest sit under "More filters", which
// opens by itself when a bookmarked view already uses one of them.
const MORE_KEYS = [
	"budget_min",
	"budget_max",
	"configuration",
	"locality",
	"timeline",
	"team",
	"consent_status",
	"last_contacted_from",
	"last_contacted_to",
	"follow_up",
	"sort",
];
const moreOpen = ref(false);
const moreActive = computed(
	() =>
		MORE_KEYS.filter((k) => filters[k] !== "" && filters[k] != null).length +
		(untouchedOnly.value ? 1 : 0)
);

// The KPI strip counts the leads in view, so it follows the filters (the list holds up to 100).
const kpis = computed(() => {
	const weekAgo = Date.now() - 7 * 24 * 3600 * 1000;
	const rows = leads.value;
	return [
		{
			label: "Total leads",
			value: rows.length,
			caption: "in this view",
			icon: "lucide-users",
		},
		{
			label: "New this week",
			value: rows.filter(
				(l) => new Date(String(l.creation).replace(" ", "T")).getTime() >= weekAgo
			).length,
			caption: "made in the last 7 days",
			icon: "lucide-calendar-plus",
			tone: "success",
		},
		{
			label: "Overdue follow ups",
			value: rows.filter((l) => l.follow_up_state === "overdue").length,
			caption: "past their date",
			icon: "lucide-clock-alert",
			tone: "danger",
		},
		{
			label: "Untouched",
			value: rows.filter((l) => l.untouched).length,
			caption: `no activity for ${untouchedDays.value} days`,
			icon: "lucide-hourglass",
			tone: "warning",
		},
	];
});

// The table (docs/UI_STANDARD.md, "Tables"). The phone number sits under the name once the list carries
// it; the list call does not return phone numbers today, so no cell is invented.
const agentName = (email) =>
	options.agents.find((a) => a.name === email)?.full_name || email || "Unassigned";
const columns = [
	{ key: "client_name", label: "Name", primary: true, sortable: true, wrap: true },
	{ key: "project", label: "Project interest", wrap: true, class: "min-w-[7rem]" },
	{ key: "source", wrap: true, label: "Source", sortable: true },
	{ key: "stage", label: "Stage", sortable: true },
	{
		key: "assigned_to",
		wrap: true,
		label: "Assigned agent",
		sortable: true,
		sortValue: (l) => agentName(l.assigned_to),
	},
	{
		key: "budget",
		label: "Budget",
		sortable: true,
		align: "right",
		sortValue: (l) => Number(l.budget || 0),
	},
	{ key: "consent_status", label: "Consent", sortable: true },
	{ key: "last_contacted", wrap: true, label: "Last activity", sortable: true },
	{ key: "next_follow_up", wrap: true, label: "Next follow up", sortable: true },
	{ key: "flags", wrap: true, label: "Flags" },
];
const consentTone = (lead) =>
	lead.consent_warning === "red"
		? "danger"
		: lead.consent_warning === "amber"
		? "warning"
		: "success";
const projectInterest = (lead) => {
	const r = lead.requirements || {};
	return [...(r.configuration || []), ...(r.preferred_localities || [])].join(", ");
};
const rowTo = (lead) => ({ path: `${basePath.value}/${lead.name}`, query: route.query });
const rowActions = (lead) => [
	{ label: "Open lead", onClick: () => router.push(rowTo(lead)) },
	{
		label: "Log a call or note",
		onClick: () =>
			router.push({ path: `${basePath.value}/${lead.name}`, query: { tab: "activity" } }),
	},
];

// Whether any filter, the search or the untouched box is on: Clear shows.
const filtersOn = computed(
	() => Object.keys(activeFilters()).length > 0 || Boolean(search.value) || untouchedOnly.value
);
function setFilter(key, value) {
	filters[key] = value;
	load();
}

// A select's first choice is "Any ..." with an empty value, so the filter is off until a choice is made.
const withAny = (label, items) => [{ label, value: "" }, ...items];
const followUpOptions = computed(() => [
	{ label: "Any follow up", value: "" },
	{ label: "Overdue follow up", value: "overdue" },
	{ label: "Has an open follow up", value: "open" },
	{ label: "No open follow up", value: "none" },
	{ label: `Untouched, no follow up for ${followUpDays.value} days`, value: "untouched" },
]);
const sortOptions = [
	{ label: "Newest change first", value: "" },
	{ label: "Next follow up first", value: "next_follow_up" },
];

// The URL keeps the view, the search and every filter, so a filtered view can be bookmarked (SOS-P1-24).
// The numbers in it are the same names the server takes, and the search is q.
function readUrl() {
	const q = route.query;
	view.value = q.view === "board" ? "board" : "list";
	search.value = typeof q.q === "string" ? q.q : "";
	for (const key of Object.keys(emptyFilters())) {
		filters[key] = typeof q[key] === "string" ? q[key] : "";
	}
	untouchedOnly.value = q.untouched === "1";
	if (moreActive.value) moreOpen.value = true;
}

function writeUrl() {
	const query = { ...activeFilters() };
	if (search.value) query.q = search.value;
	if (untouchedOnly.value) query.untouched = "1";
	if (view.value === "board") query.view = "board";
	router.replace({ path: route.path, query });
}

async function setView(next) {
	view.value = next;
	await load();
}

async function loadOptions() {
	try {
		const [opts, st, so] = await Promise.all([
			crmApi.leadFilterOptions(),
			crmApi.listStages(),
			crmApi.listLeadSources(),
		]);
		Object.assign(options, {
			agents: opts.agents || [],
			teams: opts.teams || [],
			consent_statuses: opts.consent_statuses || [],
		});
		untouchedDays.value = opts.untouched_days || 7;
		followUpDays.value = opts.follow_up_untouched_days || 3;
		stages.value = st || [];
		filterSources.value = so.sources || [];
	} catch (e) {
		logBackgroundError("lead_filter_options failed", e);
	}
}
// Bulk reassignment (SOS-P1-19): a Company Admin or Sales Manager moves the selected leads to one agent.
const canReassign = computed(
	() =>
		!partner.value &&
		(session.roles.includes("SellOS Company Admin") ||
			session.roles.includes("SellOS Sales Manager"))
);
const selected = ref([]);
const reassignAgents = ref([]);
const bulkAgent = ref("");
const bulkNotice = ref("");
const bulkError = ref("");

async function loadReassignAgents() {
	if (!canReassign.value) return;
	try {
		reassignAgents.value = (await crmApi.reassignOptions()).agents || [];
	} catch (e) {
		logBackgroundError("reassign_options failed", e);
	}
}

async function bulkReassign() {
	bulkNotice.value = "";
	bulkError.value = "";
	try {
		const result = await crmApi.bulkReassign(bulkAgent.value, selected.value);
		bulkNotice.value = `${result.count} leads reassigned. ${result.tasks_moved} follow ups and ${result.visits_moved} site visits moved with them.`;
		selected.value = [];
		await load();
	} catch (e) {
		bulkError.value = serverMessage(e, "The leads could not be reassigned.");
	}
}

const form = reactive({
	client_name: "",
	client_type: "Buyer",
	phone: "",
	overseas_phone: "",
	country_of_residence: "",
	email: "",
	source: "",
	campaign: "",
});
const sources = ref([]);
const sourceOptions = computed(() => [
	{ label: "Choose a source", value: "" },
	...sources.value.map((so) => ({ label: so.name, value: so.name })),
]);
const canManageSources = ref(false);
const newSource = ref("");

async function loadSources() {
	try {
		const result = await crmApi.listLeadSources();
		sources.value = result.sources || [];
		canManageSources.value = !!result.can_manage;
	} catch (e) {
		sources.value = [];
		logBackgroundError("list_lead_sources failed", e);
	}
}

// A Company Admin extends the list from the form. The new source is chosen at once.
async function addSource() {
	const name = newSource.value.trim();
	if (!name) return;
	error.value = "";
	try {
		const saved = await crmApi.saveLeadSource({ source_name: name });
		await loadSources();
		form.source = saved.name;
		newSource.value = "";
	} catch (e) {
		error.value = serverMessage(e, "The source could not be added.");
	}
}

function activeFilters() {
	return Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== "" && v != null));
}

function serverFilters() {
	return { ...activeFilters(), ...(untouchedOnly.value ? { untouched: 1 } : {}) };
}

async function clearFilters() {
	Object.assign(filters, emptyFilters());
	untouchedOnly.value = false;
	search.value = "";
	await load();
}

// Only the newest request may fill the screen: a slow earlier answer must not overwrite a filtered one.
let loadSeq = 0;
async function load() {
	const seq = ++loadSeq;
	loading.value = true;
	loadError.value = "";
	try {
		writeUrl();
		if (view.value === "board") {
			const result = await crmApi.getBoard(search.value, serverFilters());
			if (seq !== loadSeq) return;
			board.columns = result.columns || [];
			untouchedDays.value = result.untouched_days || untouchedDays.value;
		} else {
			const rows = (await crmApi.listLeads(search.value, 0, serverFilters())) || [];
			if (seq !== loadSeq) return;
			leads.value = rows;
		}
	} catch (e) {
		if (seq !== loadSeq) return;
		leads.value = [];
		board.columns = [];
		loadError.value = serverMessage(e, "The leads could not be loaded.");
		logBackgroundError("list_leads failed", e);
	} finally {
		if (seq === loadSeq) loading.value = false;
	}
}

const duplicates = ref([]);
const MATCH_LABELS = { phone: "phone number", overseas_phone: "overseas phone", email: "email" };
const matchLabel = (reason) => MATCH_LABELS[reason] || reason;

// Finish a lead on the client it was made for (SOS-P1-16), then show it.
async function finish(clientName, source) {
	const values = { client: clientName, source: source };
	if (form.campaign.trim()) values.campaign = form.campaign.trim();
	const saved = await crmApi.saveLead(values);
	creating.value = false;
	duplicates.value = [];
	Object.assign(form, {
		client_name: "",
		phone: "",
		overseas_phone: "",
		email: "",
		source: "",
		campaign: "",
	});
	await load();
	router.push(`${basePath.value}/${saved.lead.name}`);
}

// The first save looks for a client with the same phone, overseas phone or email and shows it. The
// agent then adds the enquiry to that client, or saves a new one anyway (SOS-P1-16).
async function create(anyway = false) {
	error.value = "";
	try {
		if (!anyway) {
			duplicates.value =
				(await crmApi.findDuplicates({
					phone: form.phone,
					overseas_phone: form.overseas_phone,
					email: form.email,
				})) || [];
			if (duplicates.value.length) return;
		}
		const { source, ...clientValues } = form;
		const client = await crmApi.saveClient(clientValues);
		await finish(client.name, source);
	} catch (e) {
		error.value = serverMessage(e, "The lead could not be saved.");
	}
}

async function addToExisting(match) {
	error.value = "";
	try {
		await finish(match.name, form.source);
	} catch (e) {
		error.value = serverMessage(e, "The lead could not be saved.");
	}
}

// Only someone who can make a lead needs the source list. A channel partner's screen never asks for
// it, so leaving that screen cuts no request off half way.
// The search dialog in the top bar asks this screen for a search while it is open (shell.searchRequest);
// from another screen it navigates here with ?q=, which readUrl reads.
watch(
	() => shell.searchRequest,
	(request) => {
		if (!request) return;
		search.value = request.q;
		load();
	}
);

onMounted(() => {
	readUrl();
	load();
	loadOptions();
	if (canCreate.value) loadSources();
	loadReassignAgents();
});
</script>
