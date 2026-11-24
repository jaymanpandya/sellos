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

		<p
			v-if="error && !creating"
			role="alert"
			data-testid="sellos-seller-error"
			class="mb-ui-md text-sm text-danger"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-seller-notice"
			class="mb-ui-md text-sm text-ink"
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

		<section v-if="stages.length" class="ui-card mb-ui-md">
			<h2 class="ui-card-heading mb-ui-sm">Sellers by stage</h2>
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
		</section>

		<DataTable
			v-if="!loadError"
			title="Seller pipeline"
			caption="Sellers"
			:columns="columns"
			:rows="sellers"
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
				<span class="block" data-testid="sellos-seller-title">{{ row.lead_title }}</span>
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
					class="mt-ui-sm space-y-1 text-sm text-ink-muted"
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
			<p
				v-if="error"
				role="alert"
				data-testid="sellos-seller-error"
				class="text-sm text-danger"
			>
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
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { crmApi, serverMessage } from "../crm/crmApi";
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
