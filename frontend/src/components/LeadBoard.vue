<template>
	<section data-testid="sellos-board" class="mt-ui-md">
		<div
			v-if="notice"
			role="status"
			data-testid="sellos-board-notice"
			:data-level="notice.level"
			class="mb-ui-md flex items-start gap-ui-sm rounded border border-line bg-surface p-ui-md text-sm text-ink"
		>
			<StatusBadge
				:tone="noticeTone(notice.level)"
				:label="notice.level === 'error' ? 'Not moved' : 'Moved, with a warning'"
			/>
			<span>{{ notice.message }}</span>
		</div>
		<form
			v-if="pending"
			class="ui-card mb-ui-md flex flex-wrap items-end gap-ui-md"
			data-testid="sellos-board-lost-form"
			@submit.prevent="confirmLost"
		>
			<FormField
				v-model="lostReason"
				type="select"
				label="Why was this lead lost?"
				required
				:options="reasonOptions"
				class="min-w-64"
				data-testid="sellos-board-lost-reason"
			/>
			<AppButton variant="primary" type="submit" data-testid="sellos-board-lost-save">
				Move to {{ pending.stage }}
			</AppButton>
			<AppButton
				type="button"
				data-testid="sellos-board-lost-cancel"
				@click="pending = null"
			>
				Cancel
			</AppButton>
		</form>
		<div class="flex gap-ui-md overflow-x-auto pb-ui-md">
			<div
				v-for="column in columns"
				:key="column.stage"
				class="w-64 shrink-0 rounded border border-line bg-surface shadow-card"
				data-testid="sellos-board-column"
				:data-stage="column.stage"
				:data-over="overStage === column.stage ? 'yes' : 'no'"
				@dragover.prevent="canMove && (overStage = column.stage)"
				@dragleave="overStage === column.stage && (overStage = '')"
				@drop.prevent="onDrop(column.stage, $event)"
			>
				<header class="border-b border-line-soft p-ui-md">
					<h2 class="ui-card-heading">{{ column.stage }}</h2>
					<p class="mt-1 text-sm text-ink-muted">
						<span data-testid="sellos-board-count">{{ column.count }}</span>
						{{ column.count === 1 ? "lead" : "leads" }}
						·
						<span
							data-testid="sellos-board-total"
							:data-rupees="column.total_budget"
							>{{ rupees(column.total_budget) }}</span
						>
					</p>
				</header>
				<ul class="min-h-[3rem] space-y-ui-sm p-ui-sm">
					<li
						v-for="lead in column.leads"
						:key="lead.name"
						class="rounded border border-line-soft bg-white p-ui-sm text-sm"
						data-testid="sellos-board-card"
						:data-lead="lead.name"
						:data-budget="lead.budget"
						:data-stage="column.stage"
						:draggable="canMove"
						@dragstart="onDragStart(lead, $event)"
						@dragend="overStage = ''"
					>
						<router-link
							:to="{ path: `${basePath}/${lead.name}`, query: $route.query }"
							class="ui-link block font-medium"
							data-testid="sellos-board-card-name"
						>
							{{ lead.client_name }}
						</router-link>
						<p class="text-sm text-ink-muted">{{ lead.source }}</p>
						<p v-if="lead.budget" class="text-sm text-ink-muted">
							{{ rupees(lead.budget) }}
						</p>
						<p class="mt-1 flex flex-wrap gap-1">
							<StatusBadge
								v-if="lead.untouched"
								data-testid="sellos-untouched"
								tone="warning"
								:label="`No activity for ${untouchedDays} days`"
							/>
							<StatusBadge
								v-if="lead.consent_status !== 'Consented'"
								data-testid="sellos-board-card-consent"
								:data-status="lead.consent_status"
								:tone="CONSENT_TONE[lead.consent_status] || 'neutral'"
								:label="lead.consent_status"
							/>
						</p>
						<FormField
							v-if="canMove"
							:model-value="column.stage"
							type="select"
							label="Move to stage"
							:options="stageOptions"
							class="mt-ui-sm"
							data-testid="sellos-board-card-move"
							@update:model-value="request(lead, $event)"
						/>
					</li>
				</ul>
			</div>
		</div>
	</section>
</template>

<script setup>
import { computed, ref } from "vue";

import AppButton from "./AppButton.vue";
import FormField from "./FormField.vue";
import StatusBadge from "./StatusBadge.vue";
import { logBackgroundError, logRequestError } from "../api";
import { crmApi, serverMessage } from "../crm/crmApi";

// The pipeline board (SOS-P1-24). A card drags to any column, or moves with the box on the card, and
// the move is move_lead_stage: any stage, whatever the consent status, with its warning shown here.
const props = defineProps({
	columns: { type: Array, required: true },
	canMove: { type: Boolean, default: false },
	basePath: { type: String, required: true },
	untouchedDays: { type: Number, default: 7 },
});
const emit = defineEmits(["moved"]);

const overStage = ref("");
const notice = ref(null);
const pending = ref(null);
const lostReason = ref("");
const lostReasons = ref([]);

const reasonOptions = computed(() => [
	{ label: "Choose a reason", value: "" },
	...lostReasons.value.map((r) => ({ label: r.name, value: r.name })),
]);
const stageOptions = computed(() =>
	props.columns.map((c) => ({ label: c.stage, value: c.stage }))
);
const CONSENT_TONE = { "Opted out": "danger", "Registered DND": "warning" };
const noticeTone = (level) => (level === "error" ? "danger" : "warning");

const rupees = (value) =>
	new Intl.NumberFormat("en-IN", {
		style: "currency",
		currency: "INR",
		maximumFractionDigits: 0,
	}).format(value || 0);

function onDragStart(lead, event) {
	event.dataTransfer?.setData("text/plain", lead.name);
}

function onDrop(stage, event) {
	overStage.value = "";
	if (!props.canMove) return;
	const name = event.dataTransfer?.getData("text/plain");
	const lead = props.columns.flatMap((c) => c.leads).find((l) => l.name === name);
	if (lead) request(lead, stage);
}

function stageType(stage) {
	return props.columns.find((c) => c.stage === stage)?.stage_type;
}

// A move to a Lost stage asks for a reason first (SOS-P1-21). Any other move goes straight through.
async function request(lead, stage) {
	const from = props.columns.find((c) => c.leads.some((l) => l.name === lead.name))?.stage;
	if (stage === from) return;
	if (stageType(stage) === "Lost") {
		try {
			if (!lostReasons.value.length) {
				lostReasons.value = (await crmApi.listLostReasons()).lost_reasons || [];
			}
		} catch (e) {
			logBackgroundError("list_lost_reasons failed", e);
		}
		lostReason.value = "";
		pending.value = { lead, stage };
		return;
	}
	await move(lead, stage, null);
}

async function confirmLost() {
	if (!lostReason.value) return;
	const { lead, stage } = pending.value;
	await move(lead, stage, lostReason.value);
}

async function move(lead, stage, reason) {
	notice.value = null;
	try {
		const result = await crmApi.moveLeadStage(lead.name, stage, reason);
		pending.value = null;
		if (result.warning) notice.value = result.warning;
		emit("moved", result);
	} catch (e) {
		pending.value = null;
		notice.value = {
			level: "error",
			message: serverMessage(e, "The lead could not be moved."),
		};
		logRequestError("move_lead_stage failed", e);
		emit("moved", null);
	}
}
</script>
