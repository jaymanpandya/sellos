<template>
	<div data-testid="sellos-sellers-page">
		<PageHeader
			title="Sellers"
			text="An owner who wants to sell is a lead on the seller pipeline, linked to a client. Move each one along the stages to a signed mandate and a sale."
			icon="lucide-home"
		/>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-seller-error"
			class="mb-ui-md text-sm text-accent"
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
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-seller-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<ListCard title="Seller pipeline">
			<div
				class="mb-ui-md flex flex-wrap gap-ui-sm"
				data-testid="sellos-seller-stage-counts"
			>
				<StatusBadge
					v-for="s in stages"
					:key="s.name"
					:tone="
						s.stage_type === 'Won'
							? 'success'
							: s.stage_type === 'Lost'
							? 'danger'
							: 'neutral'
					"
					:label="`${s.label}: ${counts[s.name] || 0}`"
					data-testid="sellos-seller-stage-count"
					:data-stage="s.label"
				/>
			</div>
			<EmptyState
				v-if="loaded && !loadError && !sellers.length"
				title="No sellers yet"
				text="Add the first seller below."
				icon="lucide-home"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-seller-list">
				<li
					v-for="l in sellers"
					:key="l.name"
					data-testid="sellos-seller-row"
					:data-name="l.name"
					:data-title="l.lead_title"
					:data-stage="labelOf(l.stage)"
					class="rounded-input border border-line-soft p-ui-md"
				>
					<div class="flex flex-wrap items-center gap-3">
						<span class="font-medium text-ink" data-testid="sellos-seller-title">{{
							l.lead_title
						}}</span>
						<StatusBadge
							tone="info"
							:label="labelOf(l.stage)"
							data-testid="sellos-seller-stage"
						/>
					</div>
					<div class="mt-ui-sm grid gap-ui-sm md:grid-cols-3">
						<FormField
							v-model="target[l.name]"
							type="select"
							label="Move to"
							:options="stageOptions"
							data-testid="sellos-seller-move-to"
						/>
						<FormField
							v-if="kindOf(target[l.name]) === 'Lost'"
							v-model="reason[l.name]"
							type="select"
							label="Lost reason"
							:options="reasonOptions"
							required
							data-testid="sellos-seller-lost-reason"
						/>
					</div>
					<div class="mt-ui-sm flex flex-wrap gap-ui-sm">
						<AppButton
							type="button"
							variant="primary"
							data-testid="sellos-seller-move"
							@click="move(l)"
						>
							Move
						</AppButton>
						<AppButton
							type="button"
							:active="shownLog === l.name"
							data-testid="sellos-seller-log-toggle"
							@click="toggleLog(l)"
						>
							Stage history
						</AppButton>
					</div>
					<ul
						v-if="shownLog === l.name"
						class="mt-ui-sm space-y-1 text-sm text-ink-muted"
						data-testid="sellos-seller-log"
					>
						<li v-if="!log.length">No stage changes yet.</li>
						<li v-for="(c, i) in log" :key="i" data-testid="sellos-seller-log-row">
							{{ c.changed_on }}: {{ c.changed_by }} moved it from
							{{ labelOf(c.from_stage) }} to {{ labelOf(c.to_stage) }}.
						</li>
					</ul>
				</li>
			</ul>
		</ListCard>

		<ListCard title="Add a seller" class="mt-ui-lg">
			<div class="grid gap-ui-md md:grid-cols-2">
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
			</div>
			<div class="mt-ui-md">
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-seller-save"
					@click="add"
				>
					Add seller
				</AppButton>
			</div>
		</ListCard>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { crmApi, serverMessage } from "../crm/crmApi";

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
		form.client = "";
		form.source = "";
		await load();
	} catch (e) {
		error.value = serverMessage(e, "The seller could not be added.");
	}
}

onMounted(load);
</script>
