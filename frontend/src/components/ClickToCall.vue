<template>
	<span>
		<AppButton
			type="button"
			variant="primary"
			data-testid="sellos-click-to-call"
			@click="openDialog"
		>
			<template #prefix
				><span class="lucide-phone icon-inherit size-4" aria-hidden="true"
			/></template>
			Call
		</AppButton>

		<Dialog v-model="shown" :options="{ title: 'Call this lead', size: 'md' }">
			<template #body-content>
				<div class="space-y-ui-md" data-testid="sellos-call-dialog" :data-step="step">
					<!-- The consent status and its warning: before the call and during it. Never a block. -->
					<div v-if="consent.status" data-testid="sellos-call-consent-box">
						<StatusBadge
							:label="consent.status"
							:tone="TONE[consent.level] || 'success'"
							data-testid="sellos-call-consent"
							:data-level="consent.level"
						/>
						<p
							v-if="consent.message"
							data-testid="sellos-call-warning"
							class="mt-ui-sm text-sm"
							:class="consent.level === 'red' ? 'text-danger' : 'text-ink-muted'"
						>
							{{ consent.message }}
						</p>
					</div>

					<p v-if="loading" class="text-sm text-ink-muted">Loading</p>
					<p
						v-if="error"
						role="alert"
						data-testid="sellos-call-error"
						class="text-sm text-danger"
					>
						{{ error }}
					</p>

					<!-- Before the call -->
					<form
						v-if="step === 'ready'"
						class="space-y-ui-md"
						data-testid="sellos-call-ready"
						@submit.prevent="start"
					>
						<p class="text-sm text-ink-muted">
							Your phone rings first. When you answer, the lead is called. Both calls
							stay in India.
						</p>
						<FormField
							v-model="purpose"
							type="select"
							label="Purpose of the call"
							:options="purposes"
							data-testid="sellos-call-purpose"
							@update:model-value="refreshPreview"
						/>
						<div class="flex justify-end gap-ui-sm">
							<AppButton type="button" @click="shown = false">Cancel</AppButton>
							<AppButton
								type="submit"
								variant="primary"
								:disabled="!canCall || starting"
								data-testid="sellos-call-start"
								>Call me, then the lead</AppButton
							>
						</div>
					</form>

					<!-- During the call -->
					<div v-else-if="step === 'calling'" data-testid="sellos-call-calling">
						<p
							data-testid="sellos-call-stage"
							:data-stage="live.stage"
							class="font-medium text-ink"
						>
							{{ live.message }}
						</p>
					</div>

					<!-- After the call: the outcome is required, so the dialog does not close until it is saved. -->
					<form
						v-else-if="step === 'outcome'"
						class="space-y-ui-md"
						data-testid="sellos-call-outcome-form"
						@submit.prevent="saveOutcome"
					>
						<p
							data-testid="sellos-call-stage"
							:data-stage="live.stage"
							class="text-ink"
						>
							{{ live.message }} How did it go?
						</p>
						<FormField
							v-model="outcome.outcome"
							type="select"
							label="Outcome"
							required
							:options="outcomeOptions"
							data-testid="sellos-call-outcome"
						/>
						<FormField
							v-model="outcome.notes"
							label="Notes"
							data-testid="sellos-call-notes"
						/>
						<FormField
							v-if="chosenOutcome?.needs_follow_up"
							v-model="outcome.followUp"
							type="datetime-local"
							label="Follow up on"
							required
							data-testid="sellos-call-follow-up"
						/>
						<div class="flex justify-end">
							<AppButton
								type="submit"
								variant="primary"
								data-testid="sellos-call-outcome-save"
								>Save outcome</AppButton
							>
						</div>
					</form>
				</div>
			</template>
		</Dialog>
	</span>
</template>

<script setup>
// Click to call (SOS-P2-07). One button, one dialog, three steps: ready (the lead's consent status and
// warning, and the purpose), calling (the status of both legs, warning still shown) and outcome (required).
// Consent never blocks: the Call button is never disabled by a consent status, only by a number that cannot
// be rung. The server decides; the screen shows what it says. A call that has ended with no outcome is asked
// for again the next time the button is on a screen (pending_outcomes).
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { Dialog } from "frappe-ui";

import { crmApi, serverMessage } from "../crm/crmApi";
import { callApi } from "../telephony/callApi";
import AppButton from "./AppButton.vue";
import FormField from "./FormField.vue";
import StatusBadge from "./StatusBadge.vue";

// checkPending: ask for the outcome of an ended call of this lead that has none (one lead page, not every row).
const props = defineProps({
	lead: { type: String, required: true },
	checkPending: { type: Boolean, default: false },
});
const emit = defineEmits(["done"]);

const TONE = { red: "danger", amber: "warning", none: "success" };
const POLL_MS = 2000;

const open = ref(false);
const step = ref("ready");
const loading = ref(false);
const starting = ref(false);
const error = ref("");
const purpose = ref("Service");
const purposes = ref(["Service"]);
const canCall = ref(false);
const consent = reactive({ status: "", level: "none", message: "" });
const live = reactive({ call_log: "", stage: "", message: "" });
const outcomes = ref([]);
const outcome = reactive({ outcome: "", notes: "", followUp: "" });
let timer = null;

// While an outcome is owed the dialog cannot be closed.
const shown = computed({
	get: () => open.value,
	set: (value) => {
		if (!value && step.value === "outcome") return;
		open.value = value;
		if (!value) stopPolling();
	},
});
const outcomeOptions = computed(() => [
	{ label: "Outcome", value: "" },
	...outcomes.value.map((row) => ({ label: row.name, value: row.name })),
]);
const chosenOutcome = computed(() => outcomes.value.find((row) => row.name === outcome.outcome));

function setConsent(view) {
	Object.assign(consent, {
		status: view.consent_status || "",
		level: view.consent_warning || "none",
		message: view.consent_message || "",
	});
}

async function refreshPreview() {
	error.value = "";
	try {
		const view = await callApi.preview(props.lead, purpose.value);
		setConsent(view);
		purposes.value = view.purposes;
		canCall.value = view.can_call;
		error.value = view.error;
	} catch (e) {
		canCall.value = false;
		error.value = serverMessage(e, "The call could not be prepared.");
	}
}

async function openDialog() {
	step.value = "ready";
	open.value = true;
	loading.value = true;
	await refreshPreview();
	loading.value = false;
}

async function start() {
	starting.value = true;
	error.value = "";
	try {
		const result = await callApi.start(props.lead, purpose.value);
		setConsent(result);
		if (result.refused) {
			error.value = result.reason;
			return;
		}
		live.call_log = result.call_log;
		step.value = "calling";
		await follow();
	} catch (e) {
		error.value = serverMessage(e, "The call could not be placed.");
	} finally {
		starting.value = false;
	}
}

function stopPolling() {
	if (timer) clearTimeout(timer);
	timer = null;
}

// Read the call's status until it ends, then ask for its outcome.
async function follow() {
	stopPolling();
	try {
		const status = await callApi.status(live.call_log);
		setConsent(status);
		Object.assign(live, { stage: status.stage, message: status.message });
		error.value = status.error;
		if (status.outcome_needed) {
			await showOutcome();
			return;
		}
	} catch (e) {
		error.value = serverMessage(e, "The call status could not be read.");
	}
	if (open.value && step.value === "calling") timer = setTimeout(follow, POLL_MS);
}

async function showOutcome() {
	if (!outcomes.value.length) outcomes.value = (await crmApi.listCallOutcomes()).outcomes;
	Object.assign(outcome, { outcome: "", notes: "", followUp: "" });
	step.value = "outcome";
	open.value = true;
}

async function saveOutcome() {
	error.value = "";
	// The outcome is required. The server refuses a blank one too; this says so without the trip.
	if (!outcome.outcome) {
		error.value = "Choose an outcome from the list.";
		return;
	}
	try {
		await callApi.recordOutcome(live.call_log, {
			outcome: outcome.outcome,
			notes: outcome.notes,
			follow_up_at: chosenOutcome.value?.needs_follow_up ? outcome.followUp : null,
		});
		step.value = "ready";
		open.value = false;
		emit("done");
	} catch (e) {
		error.value = serverMessage(e, "The outcome could not be saved.");
	}
}

// A call that ended while the screen was away still owes its outcome: ask for it now.
onMounted(async () => {
	if (!props.checkPending) return;
	try {
		const owed = (await callApi.pending()).find((row) => row.lead === props.lead);
		if (owed) {
			live.call_log = owed.call_log;
			Object.assign(live, { stage: owed.stage, message: owed.message });
			setConsent(owed);
			await showOutcome();
		}
	} catch (e) {
		// the outcome is asked for again next time
	}
});
onBeforeUnmount(stopPolling);
</script>
