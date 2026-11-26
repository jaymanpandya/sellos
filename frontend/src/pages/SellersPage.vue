<template>
	<PageTemplate data-testid="sellos-sellers-page">
		<template #header>
			<PageHeader
				title="Sellers"
				text="Owners who want to sell, moved along the seller pipeline to a signed mandate and a sale."
				icon="lucide-home"
			>
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-seller-new"
					@click="openForm"
				>
					<template #prefix
						><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
					/></template>
					Add seller
				</AppButton>
			</PageHeader>
		</template>

		<template v-if="!loadError" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-seller-stats" />
		</template>

		<template v-if="!loadError" #filters>
			<FilterBar
				v-model:search="search"
				search-label="Search sellers"
				search-placeholder="Search by seller"
				search-testid="sellos-seller-search"
				clear-testid="sellos-seller-filter-clear"
				:active="
					Boolean(search || stageFilter || sourceFilter || agentFilter || mandateFilter)
				"
				:chips="chips"
				data-testid="sellos-seller-filters"
				@clear="clearFilters"
				@remove-chip="removeChip"
			>
				<FormField
					v-model="stageFilter"
					compact
					type="select"
					label="Stage"
					:options="stageFilterOptions"
					data-testid="sellos-seller-filter-stage"
				/>
				<FormField
					v-model="sourceFilter"
					compact
					type="select"
					label="Source"
					:options="sourceFilterOptions"
					data-testid="sellos-seller-filter-source"
				/>
				<FormField
					v-model="agentFilter"
					compact
					type="select"
					label="Agent"
					:options="agentFilterOptions"
					data-testid="sellos-seller-filter-agent"
				/>
				<FormField
					v-model="mandateFilter"
					compact
					type="select"
					label="Mandate"
					:options="mandateFilterOptions"
					data-testid="sellos-seller-filter-mandate"
				/>
			</FilterBar>
		</template>

		<p
			v-if="error && !creating"
			role="alert"
			data-testid="sellos-seller-error"
			class="mb-ui-md ui-text-error"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-seller-notice"
			class="mb-ui-md ui-text-small"
		>
			{{ notice }}
		</p>
		<LoadError
			v-if="loadError"
			:message="loadError"
			class="mb-ui-md"
			data-testid="sellos-seller-load-error"
			@retry="load"
		/>

		<SectionCard v-if="stages.length" title="Sellers by stage" class="mb-ui-md">
			<div class="flex flex-wrap gap-ui-sm" data-testid="sellos-seller-stage-counts">
				<StatusBadge
					v-for="s in stages"
					:key="s.name"
					:tone="stageTone(s)"
					:label="`${s.label}: ${counts[s.name] || 0}`"
					data-testid="sellos-seller-stage-count"
					:data-stage="s.label"
				/>
			</div>
		</SectionCard>

		<p
			v-if="bulkNotice"
			role="status"
			class="mb-ui-md ui-text-small"
			data-testid="sellos-seller-bulk-result"
		>
			{{ bulkNotice }}
		</p>
		<p
			v-if="bulkError"
			role="alert"
			class="mb-ui-md ui-text-error"
			data-testid="sellos-seller-bulk-error"
		>
			{{ bulkError }}
		</p>
		<!-- The bulk bar exists only while rows are selected. -->
		<BulkBar v-if="canReassign" :count="selected.length" @clear="selected = []">
			<form class="flex flex-wrap items-end gap-ui-md" @submit.prevent="bulkReassign">
				<FormField
					v-model="bulkAgent"
					type="select"
					label="Give the selected sellers to"
					required
					:options="reassignAgents.map((a) => ({ value: a.name, label: a.full_name }))"
					class="min-w-[14rem]"
					data-testid="sellos-seller-bulk-agent"
				/>
				<AppButton
					type="submit"
					variant="primary"
					:disabled="!selected.length"
					data-testid="sellos-seller-bulk-reassign"
				>
					Reassign selected
				</AppButton>
			</form>
		</BulkBar>

		<DataTable
			v-if="!loadError"
			v-model:selected="selected"
			title="Seller pipeline"
			caption="Sellers"
			:columns="columns"
			dense
			:selectable="canReassign"
			:actions="rowActions"
			select-testid="sellos-seller-select"
			select-all-testid="sellos-seller-select-all"
			:rows="shownSellers"
			:row-to="(row) => `/crm/sellers/${row.name}`"
			:loading="!loaded"
			loading-label="Loading sellers."
			:row-name="(row) => row.lead_title"
			:row-attrs="rowAttrs"
			empty-title="No sellers yet"
			empty-text="Add the first seller to start the pipeline."
			empty-icon="lucide-home"
			testid="sellos-seller-list"
			row-testid="sellos-seller-row"
			loading-testid="sellos-seller-loading"
			empty-testid="sellos-seller-empty"
		>
			<template #cell-lead_title="{ row }">
				<span class="block" data-testid="sellos-seller-title">{{
					row.client_name || row.lead_title
				}}</span>
				<span
					v-if="row.phone"
					class="block ui-text-muted"
					data-testid="sellos-seller-phone"
					>{{ row.phone }}</span
				>
				<span v-if="row.source" class="block ui-text-muted"
					>{{ row.source
					}}<template v-if="row.assigned_to">
						· {{ agentName(row.assigned_to) }}</template
					></span
				>
			</template>
			<template #cell-mandate="{ row }">
				<StatusBadge
					v-if="mandateOf(row.name)"
					:tone="mandateOf(row.name) === 'Signed' ? 'success' : 'warning'"
					:label="`Mandate ${mandateOf(row.name)}`"
					data-testid="sellos-seller-mandate"
				/>
				<span v-else class="ui-text-muted">No mandate</span>
			</template>
			<template #cell-stage="{ row }">
				<StatusBadge
					tone="info"
					:label="labelOf(row.stage)"
					data-testid="sellos-seller-stage"
				/>
			</template>
			<template #cell-move="{ row }">
				<div class="grid gap-ui-sm">
					<FormField
						v-model="target[row.name]"
						type="select"
						label="Move to"
						:options="stageOptions"
						data-testid="sellos-seller-move-to"
					/>
					<FormField
						v-if="kindOf(target[row.name]) === 'Lost'"
						v-model="reason[row.name]"
						type="select"
						label="Lost reason"
						:options="reasonOptions"
						required
						data-testid="sellos-seller-lost-reason"
					/>
					<div>
						<AppButton
							type="button"
							variant="primary"
							data-testid="sellos-seller-move"
							@click="move(row)"
						>
							Move
						</AppButton>
					</div>
				</div>
			</template>
			<template #cell-history="{ row }">
				<AppButton
					type="button"
					:active="shownLog === row.name"
					data-testid="sellos-seller-log-toggle"
					@click="toggleLog(row)"
				>
					Stage history
				</AppButton>
				<ul
					v-if="shownLog === row.name"
					class="mt-ui-sm space-y-1 ui-text-muted"
					data-testid="sellos-seller-log"
				>
					<li v-if="!log.length">No stage changes yet.</li>
					<li v-for="(c, i) in log" :key="i" data-testid="sellos-seller-log-row">
						{{ formatWhen(c.changed_on) }}: {{ c.changed_by }} moved it from
						{{ labelOf(c.from_stage) }} to {{ labelOf(c.to_stage) }}.
					</li>
				</ul>
			</template>
		</DataTable>

		<!-- Adding a seller is a drawer: nothing is an open form under the list. -->
		<FormDrawer
			:open="creating"
			title="Add a seller"
			text="An owner who wants to sell, as a lead on the seller pipeline."
			submit-label="Add seller"
			testid="sellos-seller-form"
			submit-testid="sellos-seller-save"
			@close="closeForm"
			@submit="add"
		>
			<FormSection title="Seller">
				<FormField
					v-model="form.client"
					type="select"
					label="Client"
					:options="clientOptions"
					required
					data-testid="sellos-seller-client"
				/>
				<FormField
					v-model="form.source"
					type="select"
					label="Source"
					:options="sourceOptions"
					required
					data-testid="sellos-seller-source"
				/>
			</FormSection>
			<p v-if="error" role="alert" data-testid="sellos-seller-error" class="ui-text-error">
				{{ error }}
			</p>
		</FormDrawer>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import BulkBar from "../components/BulkBar.vue";
import FilterBar from "../components/FilterBar.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import SectionCard from "../components/SectionCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { crmApi, serverMessage } from "../crm/crmApi";
import { mandateApi } from "../crm/mandatesApi";
import { useRouter } from "vue-router";
import { session } from "../session";
import { formatWhen } from "../format";

// The seller pipeline (SOS-P4-04). Every move is made on the server and the list read back, so what is shown
// is what is saved. A move to Closed lost asks for a reason.
const sellers = ref([]);
const stages = ref([]);
const clients = ref([]);
const sources = ref([]);
const reasons = ref([]);
const target = reactive({});
const reason = reactive({});
const form = reactive({ client: "", source: "" });
const shownLog = ref("");
const log = ref([]);
const error = ref("");
const notice = ref("");
const loadError = ref("");
const loaded = ref(false);
const router = useRouter();
const search = ref("");
const stageFilter = ref("");
const sourceFilter = ref("");
const agentFilter = ref("");
const mandateFilter = ref("");
const mandates = reactive({}); // lead -> Draft or Signed
const mandateOf = (lead) => mandates[lead] || "";
const shownSellers = computed(() => {
	const q = search.value.trim().toLowerCase();
	return sellers.value.filter(
		(l) =>
			(!q || `${l.lead_title} ${l.client_name}`.toLowerCase().includes(q)) &&
			(!stageFilter.value || l.stage === stageFilter.value) &&
			(!sourceFilter.value || l.source === sourceFilter.value) &&
			(!agentFilter.value || l.assigned_to === agentFilter.value) &&
			(!mandateFilter.value ||
				(mandateFilter.value === "none"
					? !mandateOf(l.name)
					: mandateOf(l.name) === mandateFilter.value))
	);
});
const stageFilterOptions = computed(() => [
	{ label: "Any stage", value: "" },
	...stages.value.map((s) => ({ label: s.label, value: s.name })),
]);
const sourceFilterOptions = computed(() => [
	{ label: "Any source", value: "" },
	...[...new Set(sellers.value.map((l) => l.source).filter(Boolean))]
		.sort()
		.map((s) => ({ label: s, value: s })),
]);
const agentFilterOptions = computed(() => [
	{ label: "Any agent", value: "" },
	...[
		...new Map(
			sellers.value
				.filter((l) => l.assigned_to)
				.map((l) => [l.assigned_to, agentName(l.assigned_to)])
		),
	].map(([value, label]) => ({ label, value })),
]);
const mandateFilterOptions = [
	{ label: "Any mandate", value: "" },
	{ label: "No mandate", value: "none" },
	{ label: "Draft", value: "Draft" },
	{ label: "Signed", value: "Signed" },
];
const chips = computed(() => [
	...(search.value ? [{ key: "search", label: `Seller: ${search.value}` }] : []),
	...(stageFilter.value
		? [{ key: "stage", label: `Stage: ${labelOf(stageFilter.value)}` }]
		: []),
	...(sourceFilter.value ? [{ key: "source", label: `Source: ${sourceFilter.value}` }] : []),
	...(agentFilter.value
		? [{ key: "agent", label: `Agent: ${agentName(agentFilter.value)}` }]
		: []),
	...(mandateFilter.value
		? [
				{
					key: "mandate",
					label: `Mandate: ${
						mandateFilter.value === "none" ? "none" : mandateFilter.value
					}`,
				},
		  ]
		: []),
]);
function clearFilters() {
	search.value =
		stageFilter.value =
		sourceFilter.value =
		agentFilter.value =
		mandateFilter.value =
			"";
}
function removeChip(key) {
	const refs = {
		search,
		stage: stageFilter,
		source: sourceFilter,
		agent: agentFilter,
		mandate: mandateFilter,
	};
	refs[key].value = "";
}

// Bulk reassignment (SOS-P1-19): a Company Admin or Sales Manager moves the selected sellers to one agent.
const canReassign = computed(
	() =>
		session.roles.includes("SellOS Company Admin") ||
		session.roles.includes("SellOS Sales Manager")
);
const selected = ref([]);
const reassignAgents = ref([]);
const agentName = (email) =>
	reassignAgents.value.find((a) => a.name === email)?.full_name || email;
const bulkAgent = ref("");
const bulkNotice = ref("");
const bulkError = ref("");
async function bulkReassign() {
	bulkNotice.value = bulkError.value = "";
	try {
		const result = await crmApi.bulkReassign(bulkAgent.value, selected.value);
		bulkNotice.value = `${result.count} sellers reassigned.`;
		selected.value = [];
		await load();
	} catch (e) {
		bulkError.value = serverMessage(e, "The sellers could not be reassigned.");
	}
}
const rowActions = (row) => [
	{ label: "Open seller", onClick: () => router.push(`/crm/sellers/${row.name}`) },
	{ label: "Stage history", onClick: () => toggleLog(row) },
];

// Where each seller's mandate stands. A Company Admin or Agent reads the mandates; a Sales Manager gets only the id
// and status of its own team's mandates.
async function loadMandates(list) {
	for (const key of Object.keys(mandates)) delete mandates[key];
	try {
		if (session.roles.includes("SellOS Sales Manager")) {
			for (const m of (await mandateApi.status(list.map((l) => l.name))).mandates)
				mandates[m.lead] = m.status;
		} else {
			for (const m of (await mandateApi.overview()).mandates) mandates[m.lead] = m.status;
		}
	} catch {
		// The column then reads "No mandate": a seller list does not fail because mandates could not be read.
	}
}
const creating = ref(false);

const stageOptions = computed(() => stages.value.map((s) => ({ label: s.label, value: s.name })));
const clientOptions = computed(() => [
	{ label: "Choose a client", value: "" },
	...clients.value.map((c) => ({ label: c.client_name, value: c.name })),
]);
const sourceOptions = computed(() => [
	{ label: "Choose a source", value: "" },
	...sources.value.map((s) => ({ label: s.name, value: s.name })),
]);
const reasonOptions = computed(() => [
	{ label: "Choose a reason", value: "" },
	...reasons.value.map((r) => ({ label: r.name, value: r.name })),
]);
const counts = computed(() => {
	const out = {};
	for (const l of sellers.value) out[l.stage] = (out[l.stage] || 0) + 1;
	return out;
});
const stageTone = (s) =>
	s.stage_type === "Won" ? "success" : s.stage_type === "Lost" ? "danger" : "neutral";

// The strip counts the sellers by the kind of stage they stand on.
const kpis = computed(() => {
	const kind = (l) => stages.value.find((s) => s.name === l.stage)?.stage_type || "";
	const rows = sellers.value;
	return [
		{
			label: "Sellers",
			value: rows.length,
			caption: "on the seller pipeline",
			icon: "lucide-home",
		},
		{
			label: "In progress",
			value: rows.filter((l) => kind(l) !== "Won" && kind(l) !== "Lost").length,
			caption: "still moving along the stages",
			icon: "lucide-loader",
		},
		{
			label: "Won",
			value: rows.filter((l) => kind(l) === "Won").length,
			caption: "sold",
			icon: "lucide-trophy",
			tone: "success",
		},
		{
			label: "Lost",
			value: rows.filter((l) => kind(l) === "Lost").length,
			caption: "closed without a sale",
			icon: "lucide-ban",
			tone: "danger",
		},
	];
});

// The table: the title opens nothing, so every control sits in its own cell.
const columns = [
	{ key: "lead_title", label: "Seller", primary: true, sortable: true },
	{
		key: "stage",
		label: "Stage",
		sortable: true,
		sortValue: (l) => labelOf(l.stage),
	},
	{ key: "mandate", label: "Mandate", sortable: true, sortValue: (l) => mandateOf(l.name) },
	{ key: "move", label: "Move to", wrap: true, class: "min-w-[14rem]" },
	{ key: "history", label: "History", wrap: true, class: "min-w-[12rem]" },
];
const rowAttrs = (l) => ({
	"data-title": l.lead_title,
	"data-stage": labelOf(l.stage),
});

function openForm() {
	error.value = "";
	creating.value = true;
}
function closeForm() {
	error.value = "";
	creating.value = false;
}

const labelOf = (name) => stages.value.find((s) => s.name === name)?.label || name || "";
const kindOf = (name) => stages.value.find((s) => s.name === name)?.stage_type || "";

async function load() {
	loadError.value = "";
	try {
		const [list, st, cl, so, lr] = await Promise.all([
			crmApi.listLeads("", 0, { pipeline: "Seller" }),
			crmApi.listStages("Seller"),
			crmApi.listClients(),
			crmApi.listLeadSources(),
			crmApi.listLostReasons(),
		]);
		sellers.value = list;
		stages.value = st;
		clients.value = cl;
		sources.value = so.sources;
		reasons.value = lr.lost_reasons;
		for (const l of list) {
			if (!target[l.name]) target[l.name] = l.stage;
		}
		await loadMandates(list);
		if (canReassign.value && !reassignAgents.value.length)
			reassignAgents.value = (await crmApi.reassignOptions()).agents || [];
	} catch (e) {
		loadError.value = serverMessage(e, "The sellers could not be loaded.");
	} finally {
		loaded.value = true;
	}
}

async function move(l) {
	error.value = "";
	notice.value = "";
	try {
		const result = await crmApi.moveLeadStage(l.name, target[l.name], reason[l.name] || null);
		notice.value = result.moved
			? `${l.lead_title} moved to ${labelOf(result.stage)}.`
			: `${l.lead_title} is already on ${labelOf(result.stage)}.`;
		await load();
		if (shownLog.value === l.name) await showLog(l);
	} catch (e) {
		error.value = serverMessage(e, "The seller could not be moved.");
	}
}

async function showLog(l) {
	const lead = await crmApi.getLead(l.name);
	log.value = lead.pipeline.log;
}

async function toggleLog(l) {
	if (shownLog.value === l.name) {
		shownLog.value = "";
		return;
	}
	try {
		await showLog(l);
		shownLog.value = l.name;
	} catch (e) {
		error.value = serverMessage(e, "The history could not be loaded.");
	}
}

async function add() {
	error.value = "";
	notice.value = "";
	if (!form.client || !form.source) {
		error.value = "Choose a client and a source.";
		return;
	}
	try {
		await crmApi.saveLead({ client: form.client, source: form.source, pipeline: "Seller" });
		notice.value = "The seller is added on the first stage.";
		creating.value = false;
		form.client = "";
		form.source = "";
		await load();
	} catch (e) {
		error.value = serverMessage(e, "The seller could not be added.");
	}
}

onMounted(load);
</script>
