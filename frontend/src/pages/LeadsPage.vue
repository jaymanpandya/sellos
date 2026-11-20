<template>
	<div data-testid="sellos-leads-page" :data-view="view">
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
				@click="creating = !creating"
			>
				<template #prefix
					><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
				/></template>
				{{ creating ? "Cancel" : "New lead" }}
			</AppButton>
		</PageHeader>

		<div
			v-if="view === 'list' && !loadError"
			class="mb-ui-md grid grid-cols-2 gap-ui-md md:grid-cols-4"
			data-testid="sellos-leads-stats"
		>
			<StatCard label="Total leads" :value="stats.total" icon="lucide-users" />
			<StatCard
				label="New this week"
				:value="stats.newThisWeek"
				icon="lucide-calendar-plus"
				tone="success"
			/>
			<StatCard
				label="Overdue follow ups"
				:value="stats.overdue"
				icon="lucide-clock-alert"
				tone="danger"
			/>
			<StatCard
				label="Untouched"
				:value="stats.untouched"
				icon="lucide-hourglass"
				tone="warning"
			/>
		</div>

		<form
			v-if="creating"
			class="ui-card mb-ui-md"
			data-testid="sellos-lead-form"
			@submit.prevent="create(false)"
		>
			<h2 class="ui-card-heading mb-ui-md">New lead</h2>
			<div class="grid grid-cols-1 gap-x-ui-md gap-y-ui-md md:grid-cols-2">
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
			</div>
			<section
				v-if="duplicates.length"
				role="alert"
				data-testid="sellos-duplicate-warning"
				class="mt-ui-md space-y-ui-md rounded-card border border-tone-warning-line bg-tone-warning-bg p-ui-md text-sm text-tone-warning"
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
					class="rounded-card border border-line bg-surface p-ui-md text-ink"
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
			<p
				v-if="error"
				data-testid="sellos-lead-form-error"
				class="mt-ui-md text-sm text-danger"
			>
				{{ error }}
			</p>
			<div class="mt-ui-md">
				<AppButton type="submit" variant="primary" data-testid="sellos-lead-form-save">
					Save lead
				</AppButton>
			</div>
		</form>

		<FilterBar
			:open="moreOpen"
			data-testid="sellos-leads-filters"
			@apply="load"
			@clear="clearFilters"
		>
			<FormField
				:model-value="search"
				label="Search leads"
				data-testid="sellos-leads-search"
				@update:model-value="
					(v) => {
						search = v;
						load();
					}
				"
			/>
			<FormField
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
				@update:model-value="
					(v) => {
						filters.stage = v;
						load();
					}
				"
			/>
			<FormField
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
				@update:model-value="
					(v) => {
						filters.assigned_to = v;
						load();
					}
				"
			/>
			<FormField
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
				@update:model-value="
					(v) => {
						filters.source = v;
						load();
					}
				"
			/>
			<template #more>
				<MoneyField
					v-model="filters.budget_min"
					label="Budget from (₹)"
					data-testid="sellos-leads-filter-budget-min"
				/>
				<MoneyField
					v-model="filters.budget_max"
					label="Budget to (₹)"
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
					@update:model-value="
						(v) => {
							filters.team = v;
							load();
						}
					"
				/>
				<FormField
					:model-value="filters.consent_status"
					type="select"
					label="Consent status"
					:options="withAny('Any consent status', options.consent_statuses)"
					data-testid="sellos-leads-filter-consent"
					@update:model-value="
						(v) => {
							filters.consent_status = v;
							load();
						}
					"
				/>
				<FormField
					:model-value="filters.last_contacted_from"
					type="date"
					label="Last contacted from"
					data-testid="sellos-leads-filter-contacted-from"
					@update:model-value="
						(v) => {
							filters.last_contacted_from = v;
							load();
						}
					"
				/>
				<FormField
					:model-value="filters.last_contacted_to"
					type="date"
					label="Last contacted to"
					data-testid="sellos-leads-filter-contacted-to"
					@update:model-value="
						(v) => {
							filters.last_contacted_to = v;
							load();
						}
					"
				/>
				<FormField
					:model-value="filters.follow_up"
					type="select"
					label="Follow up"
					:options="followUpOptions"
					data-testid="sellos-leads-filter-follow-up"
					@update:model-value="
						(v) => {
							filters.follow_up = v;
							load();
						}
					"
				/>
				<FormField
					:model-value="filters.sort"
					type="select"
					label="Sort"
					:options="sortOptions"
					data-testid="sellos-leads-sort"
					@update:model-value="
						(v) => {
							filters.sort = v;
							load();
						}
					"
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
			<template #actions>
				<AppButton type="submit" variant="primary" data-testid="sellos-leads-filter-apply">
					Filter
				</AppButton>
				<AppButton
					type="button"
					:aria-expanded="moreOpen ? 'true' : 'false'"
					data-testid="sellos-leads-filters-toggle"
					@click="moreOpen = !moreOpen"
				>
					<template #prefix>
						<span
							:class="moreOpen ? 'lucide-chevron-up' : 'lucide-chevron-down'"
							class="icon-inherit size-4"
							aria-hidden="true"
						/>
					</template>
					{{ moreOpen ? "Fewer filters" : "More filters" }}
					<span
						v-if="moreActive && !moreOpen"
						class="ml-1 rounded-badge bg-brand px-1.5 text-xs text-on-brand-accent"
						data-testid="sellos-leads-filters-more-count"
						>{{ moreActive }}</span
					>
				</AppButton>
				<AppButton
					type="button"
					data-testid="sellos-leads-filter-clear"
					@click="clearFilters"
				>
					Clear filters
				</AppButton>
			</template>
		</FilterBar>

		<LoadError
			v-if="loadError"
			:message="loadError"
			class="mb-ui-md"
			data-testid="sellos-leads-error"
			@retry="load"
		/>
		<ListCard v-else-if="loading" class="mb-ui-md">
			<LoadingSkeleton :rows="4" label="Loading leads." data-testid="sellos-leads-loading" />
		</ListCard>
		<EmptyState
			v-else-if="view === 'list' && !leads.length"
			title="No leads yet"
			text="Leads you may see will be listed here. Try clearing the filters, or add a lead."
			icon="lucide-users"
			data-testid="sellos-leads-empty"
		/>
		<LeadBoard
			v-if="view === 'board' && !loadError"
			:columns="board.columns"
			:can-move="!partner"
			:base-path="basePath"
			:untouched-days="untouchedDays"
			@moved="load"
		/>
		<form
			v-if="view === 'list' && canReassign && leads.length"
			class="ui-card mb-ui-md flex flex-wrap items-end gap-ui-md"
			data-testid="sellos-bulk"
			@submit.prevent="bulkReassign"
		>
			<FormField
				type="checkbox"
				:model-value="allSelected"
				:label="`Select all ${leads.length} shown`"
				data-testid="sellos-bulk-select-all"
				@update:model-value="toggleAll"
			/>
			<span class="pb-3 text-sm text-ink-muted" data-testid="sellos-bulk-count">
				{{ selected.length }} selected
			</span>
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
			<p
				v-if="bulkNotice"
				role="status"
				class="w-full text-sm text-ink"
				data-testid="sellos-bulk-result"
			>
				{{ bulkNotice }}
			</p>
			<p
				v-if="bulkError"
				role="alert"
				class="w-full text-sm text-danger"
				data-testid="sellos-bulk-error"
			>
				{{ bulkError }}
			</p>
		</form>
		<ListCard
			v-if="view === 'list' && leads.length"
			title="All leads"
			data-testid="sellos-leads-list"
		>
			<div class="-mx-ui-md sm:-mx-ui-lg">
				<div
					class="hidden items-center gap-ui-md border-b border-line px-ui-md py-2 text-xs font-semibold uppercase tracking-[0.06em] text-ink-muted sm:px-ui-lg md:grid md:grid-cols-[minmax(0,2fr)_minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1.3fr)_minmax(0,2fr)]"
					:class="canReassign ? 'md:pl-[4.25rem]' : ''"
					role="row"
				>
					<span>Name</span>
					<span>Source</span>
					<span>Stage</span>
					<span>Next follow up</span>
					<span>Flags</span>
				</div>
				<ul>
					<li
						v-for="lead in leads"
						:key="lead.name"
						data-testid="sellos-lead-row"
						class="flex items-center border-b border-line-soft last:border-b-0"
					>
						<AppCheckbox
							v-if="canReassign"
							:model-value="selected.includes(lead.name)"
							:value="lead.name"
							:aria-label="`Select ${lead.client_name}`"
							class="ml-ui-sm"
							data-testid="sellos-lead-select"
							@update:model-value="toggleSelected(lead.name, $event)"
						/>
						<router-link
							:to="{ path: `${basePath}/${lead.name}`, query: $route.query }"
							class="grid flex-1 grid-cols-1 items-center gap-x-ui-md gap-y-1 px-ui-md py-ui-md hover:bg-brand-soft sm:px-ui-lg md:grid-cols-[minmax(0,2fr)_minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1.3fr)_minmax(0,2fr)]"
						>
							<span class="truncate font-medium text-ink">{{
								lead.client_name
							}}</span>
							<span
								class="truncate text-sm text-ink-muted"
								data-testid="sellos-lead-source"
								>{{
									lead.campaign
										? `${lead.source} · ${lead.campaign}`
										: lead.source
								}}</span
							>
							<span>
								<StatusBadge
									v-if="lead.stage"
									:label="lead.stage"
									tone="neutral"
									data-testid="sellos-lead-row-stage"
								/>
							</span>
							<span class="text-sm text-ink-muted">
								<span
									v-if="lead.next_follow_up"
									data-testid="sellos-lead-next-follow-up"
									:data-state="lead.follow_up_state"
								>
									Next follow up {{ shortWhen(lead.next_follow_up) }}
								</span>
							</span>
							<span class="flex flex-wrap items-center gap-ui-sm">
								<StatusBadge
									v-if="lead.untouched"
									tone="warning"
									data-testid="sellos-untouched"
								>
									No activity for {{ untouchedDays }} days
								</StatusBadge>
								<StatusBadge
									v-if="lead.follow_up_state === 'overdue'"
									tone="danger"
									data-testid="sellos-follow-up-overdue"
								>
									Follow up overdue
								</StatusBadge>
								<StatusBadge
									v-if="lead.follow_up_untouched"
									tone="warning"
									data-testid="sellos-follow-up-untouched"
								>
									Untouched, no follow up for {{ followUpDays }} days
								</StatusBadge>
								<StatusBadge
									v-if="lead.overdue_tasks"
									tone="danger"
									data-testid="sellos-lead-overdue"
								>
									{{ lead.overdue_tasks }} overdue
								</StatusBadge>
							</span>
						</router-link>
					</li>
				</ul>
			</div>
		</ListCard>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { CLIENT_TYPES, CONFIGURATIONS, TIMELINES, crmApi, serverMessage } from "../crm/crmApi";
import { logRequestError } from "../api";
import AppButton from "../components/AppButton.vue";
import AppCheckbox from "../components/AppCheckbox.vue";
import EmptyState from "../components/EmptyState.vue";
import FilterBar from "../components/FilterBar.vue";
import FormField from "../components/FormField.vue";
import MoneyField from "../components/MoneyField.vue";
import LeadBoard from "../components/LeadBoard.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import StatCard from "../components/StatCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
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

// The numbers above the list count the leads in view, so they follow the filters (the list holds up to 100).
const stats = computed(() => {
	const weekAgo = Date.now() - 7 * 24 * 3600 * 1000;
	return {
		total: leads.value.length,
		newThisWeek: leads.value.filter(
			(l) => new Date(String(l.creation).replace(" ", "T")).getTime() >= weekAgo
		).length,
		overdue: leads.value.filter((l) => l.follow_up_state === "overdue").length,
		untouched: leads.value.filter((l) => l.untouched).length,
	};
});

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
		logRequestError("lead_filter_options failed", e);
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
const allSelected = computed(
	() => leads.value.length > 0 && selected.value.length === leads.value.length
);

function toggleSelected(name, on) {
	selected.value = on
		? [...selected.value.filter((n) => n !== name), name]
		: selected.value.filter((n) => n !== name);
}

function toggleAll(on) {
	selected.value = on ? leads.value.map((lead) => lead.name) : [];
}

async function loadReassignAgents() {
	if (!canReassign.value) return;
	try {
		reassignAgents.value = (await crmApi.reassignOptions()).agents || [];
	} catch (e) {
		logRequestError("reassign_options failed", e);
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
		logRequestError("list_lead_sources failed", e);
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
		logRequestError("list_leads failed", e);
	} finally {
		if (seq === loadSeq) loading.value = false;
	}
}

// A follow up's day, and its time when it has one: "2030-03-04 10:30" shows as "4 Mar, 10:30".
function shortWhen(value) {
	const text = String(value || "");
	const [day, time] = text.split(/[ T]/);
	const date = new Date(`${day}T00:00:00`);
	if (Number.isNaN(date.getTime())) return text;
	const label = date.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
	return time && time !== "00:00:00" ? `${label}, ${time.slice(0, 5)}` : label;
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
