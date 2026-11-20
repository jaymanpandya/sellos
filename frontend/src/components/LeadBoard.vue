<template>
	<section data-testid="sellos-board" class="mt-4">
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-board-notice"
			:data-level="notice.level"
			class="mb-3 rounded-input border border-line bg-surface p-3 text-sm text-ink"
		>
			{{ notice.message }}
		</p>
		<form
			v-if="pending"
			class="mb-3 flex flex-wrap items-center gap-2 rounded-input border border-line bg-surface p-3"
			data-testid="sellos-board-lost-form"
			@submit.prevent="confirmLost"
		>
			<label class="text-sm text-ink-muted" for="sellos-board-lost-reason">
				Why was this lead lost?
			</label>
			<select
				id="sellos-board-lost-reason"
				v-model="lostReason"
				required
				class="field w-auto"
				data-testid="sellos-board-lost-reason"
			>
				<option value="" disabled>Choose a reason</option>
				<option v-for="r in lostReasons" :key="r.name" :value="r.name">
					{{ r.name }}
				</option>
			</select>
			<button type="submit" class="btn" data-testid="sellos-board-lost-save">
				Move to {{ pending.stage }}
			</button>
			<button type="button" class="btn" @click="pending = null">Cancel</button>
		</form>
		<div class="flex gap-3 overflow-x-auto pb-3">
			<div
				v-for="column in columns"
				:key="column.stage"
				class="w-60 shrink-0 rounded-input border border-line bg-surface"
				data-testid="sellos-board-column"
				:data-stage="column.stage"
				:data-over="overStage === column.stage ? 'yes' : 'no'"
				@dragover.prevent="canMove && (overStage = column.stage)"
				@dragleave="overStage === column.stage && (overStage = '')"
				@drop.prevent="onDrop(column.stage, $event)"
			>
				<header class="border-b border-line p-3">
					<h2 class="text-sm font-semibold text-ink">{{ column.stage }}</h2>
					<p class="text-xs text-ink-muted">
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
				<ul class="min-h-[3rem] space-y-2 p-2">
					<li
						v-for="lead in column.leads"
						:key="lead.name"
						class="rounded-input border border-line bg-white p-2 text-sm"
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
							class="block font-medium text-ink"
							data-testid="sellos-board-card-name"
						>
							{{ lead.client_name }}
						</router-link>
						<p class="text-xs text-ink-muted">{{ lead.source }}</p>
						<p v-if="lead.budget" class="text-xs text-ink-muted">
							{{ rupees(lead.budget) }}
						</p>
						<p class="mt-1 flex flex-wrap gap-1">
							<span
								v-if="lead.untouched"
								data-testid="sellos-untouched"
								class="rounded-badge border border-tone-warning-line bg-tone-warning-bg px-2 py-0.5 text-xs text-tone-warning"
							>
								No activity for {{ untouchedDays }} days
							</span>
							<span
								v-if="lead.consent_status !== 'Consented'"
								data-testid="sellos-board-card-consent"
								:data-status="lead.consent_status"
								class="rounded-input border border-line px-2 py-0.5 text-xs text-ink-muted"
							>
								{{ lead.consent_status }}
							</span>
						</p>
						<select
							v-if="canMove"
							:value="column.stage"
							class="field mt-2"
							aria-label="Move to stage"
							data-testid="sellos-board-card-move"
							@change="request(lead, $event.target.value)"
						>
							<option v-for="c in columns" :key="c.stage" :value="c.stage">
								{{ c.stage }}
							</option>
						</select>
					</li>
				</ul>
			</div>
		</div>
	</section>
</template>

<script setup>
import { ref } from "vue";

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
