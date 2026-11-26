<template>
	<PageTemplate shape="record" data-testid="sellos-seller-page">
		<template #header>
			<RecordHeader
				:title="lead ? lead.lead_title : 'Seller'"
				:line="line"
				back-to="/crm/sellers"
				back-label="Back to sellers"
				title-testid="sellos-seller-title"
			>
				<template v-if="lead" #status>
					<StatusBadge
						tone="info"
						:label="labelOf(lead.stage)"
						data-testid="sellos-seller-stage"
					/>
				</template>
			</RecordHeader>
		</template>

		<LoadError
			v-if="loadError"
			:message="loadError"
			data-testid="sellos-seller-load-error"
			@retry="load"
		/>
		<LoadingSkeleton v-else-if="!loaded" :rows="4" label="Loading the seller." />

		<template v-if="lead">
			<p v-if="error" role="alert" data-testid="sellos-seller-error" class="ui-text-error">
				{{ error }}
			</p>
			<p
				v-if="notice"
				role="status"
				data-testid="sellos-seller-notice"
				class="ui-text-small"
			>
				{{ notice }}
			</p>

			<SectionCard title="Seller" help="The owner and where the enquiry came from.">
				<dl>
					<FieldGrid>
						<ReadField label="Client" :value="client.client_name" />
						<ReadField label="Source" :value="lead.source" />
						<ReadField label="Assigned to" :value="lead.assigned_to" />
						<ReadField label="Added on" :value="formatWhen(lead.creation)" />
						<ReadField label="Email" :value="client.email" />
						<ReadField label="City" :value="client.city" />
					</FieldGrid>
				</dl>
			</SectionCard>

			<NotesPanel :lead="route.params.name" />

			<SectionCard
				title="Move along the pipeline"
				help="A move to Closed lost asks for a reason."
			>
				<div class="grid gap-ui-sm md:max-w-md">
					<FormField
						v-model="target"
						type="select"
						label="Move to"
						:options="stageOptions"
						data-testid="sellos-seller-move-to"
					/>
					<FormField
						v-if="kindOf(target) === 'Lost'"
						v-model="reason"
						type="select"
						label="Lost reason"
						:options="reasonOptions"
						required
						data-testid="sellos-seller-lost-reason"
					/>
				</div>
				<template #footer>
					<AppButton
						type="button"
						variant="primary"
						data-testid="sellos-seller-move"
						@click="move"
					>
						Move
					</AppButton>
				</template>
			</SectionCard>
		</template>

		<template #side>
			<SectionCard title="Summary">
				<dl v-if="lead">
					<FieldGrid :columns="1">
						<ReadField label="Stage" :value="labelOf(lead.stage)" />
						<ReadField label="Pipeline" value="Seller" />
						<ReadField label="Lost reason" :value="lead.lost_reason" />
						<ReadField label="Mandate">
							<router-link
								v-if="mandate"
								:to="`/crm/mandates/${mandate.name}`"
								class="ui-link"
								data-testid="sellos-seller-mandate-link"
							>
								{{ mandate.status }}, open the mandate
							</router-link>
							<span v-else class="ui-text-muted">Not filled in</span>
						</ReadField>
					</FieldGrid>
				</dl>
				<p v-else class="ui-text-muted">The seller is loading.</p>
			</SectionCard>
			<SectionCard title="Stage history">
				<ul class="space-y-1 ui-text-muted" data-testid="sellos-seller-log">
					<li v-if="!log.length">No stage changes yet.</li>
					<li v-for="(c, i) in log" :key="i" data-testid="sellos-seller-log-row">
						{{ formatWhen(c.changed_on) }}: {{ c.changed_by }} moved it from
						{{ labelOf(c.from_stage) }} to {{ labelOf(c.to_stage) }}.
					</li>
				</ul>
			</SectionCard>
		</template>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import AppButton from "../components/AppButton.vue";
import FieldGrid from "../components/FieldGrid.vue";
import FormField from "../components/FormField.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import NotesPanel from "../components/NotesPanel.vue";
import PageTemplate from "../components/PageTemplate.vue";
import ReadField from "../components/ReadField.vue";
import RecordHeader from "../components/RecordHeader.vue";
import SectionCard from "../components/SectionCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { crmApi, serverMessage } from "../crm/crmApi";
import { mandateApi } from "../crm/mandatesApi";
import { formatWhen } from "../format";

// One seller (SOS-P4-04) on its own page: its stage, the move along the seller pipeline and the stage history.
// Every move is made on the server and the record read back.
const route = useRoute();
const lead = ref(null);
const client = ref({});
const log = ref([]);
const stages = ref([]);
const reasons = ref([]);
const mandate = ref(null);
const target = ref("");
const reason = ref("");
const error = ref("");
const notice = ref("");
const loadError = ref("");
const loaded = ref(false);

const labelOf = (name) => stages.value.find((s) => s.name === name)?.label || name || "";
const kindOf = (name) => stages.value.find((s) => s.name === name)?.stage_type || "";
const line = computed(() =>
	lead.value ? [client.value.client_name, lead.value.source].filter(Boolean).join(", ") : ""
);
const stageOptions = computed(() => stages.value.map((s) => ({ label: s.label, value: s.name })));
const reasonOptions = computed(() => [
	{ label: "Choose a reason", value: "" },
	...reasons.value.map((r) => ({ label: r.name, value: r.name })),
]);

async function load() {
	loadError.value = "";
	try {
		const [view, st, lr] = await Promise.all([
			crmApi.getLead(route.params.name),
			crmApi.listStages("Seller"),
			crmApi.listLostReasons(),
		]);
		lead.value = view.lead;
		client.value = view.client || {};
		log.value = view.pipeline.log;
		stages.value = st;
		reasons.value = lr.lost_reasons;
		target.value = view.lead.stage;
		mandate.value = await findMandate(view.lead.name);
	} catch (e) {
		loadError.value = serverMessage(e, "The seller could not be loaded.");
	} finally {
		loaded.value = true;
	}
}

// The mandate of this seller, when there is one. A failure here only hides the link.
async function findMandate(leadName) {
	try {
		const result = await mandateApi.overview();
		return result.mandates.find((m) => m.lead === leadName) || null;
	} catch {
		return null;
	}
}

async function move() {
	error.value = "";
	notice.value = "";
	try {
		const result = await crmApi.moveLeadStage(
			lead.value.name,
			target.value,
			reason.value || null
		);
		notice.value = result.moved
			? `${lead.value.lead_title} moved to ${labelOf(result.stage)}.`
			: `${lead.value.lead_title} is already on ${labelOf(result.stage)}.`;
		await load();
	} catch (e) {
		error.value = serverMessage(e, "The seller could not be moved.");
	}
}

onMounted(load);
</script>
