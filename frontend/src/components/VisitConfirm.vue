<template>
	<div class="flex flex-wrap items-end gap-ui-sm" data-testid="sellos-visit-confirm">
		<FormField
			:model-value="visit.confirmation_status"
			type="select"
			label="Confirmation"
			:options="confirmations"
			data-testid="sellos-visit-confirm-status"
			:disabled="visit.status === 'Done'"
			@update:model-value="choose"
		/>
		<form
			v-if="rescheduling"
			class="flex flex-wrap items-end gap-ui-sm"
			data-testid="sellos-visit-reschedule-form"
			@submit.prevent="save('Rescheduled', when)"
		>
			<FormField
				v-model="when"
				required
				type="datetime-local"
				label="New date and time"
				data-testid="sellos-visit-reschedule-when"
			/>
			<AppButton type="submit" variant="primary" data-testid="sellos-visit-reschedule-save">
				Reschedule
			</AppButton>
			<AppButton
				type="button"
				data-testid="sellos-visit-reschedule-cancel"
				@click="cancelReschedule"
			>
				Cancel
			</AppButton>
		</form>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-visit-confirm-error"
			class="text-sm text-tone-danger"
		>
			{{ error }}
		</p>
	</div>
</template>

<script setup>
import { ref } from "vue";

import { crmApi, serverMessage } from "../crm/crmApi";
import AppButton from "./AppButton.vue";
import FormField from "./FormField.vue";

// The confirmation of one site visit, set by the agent after the call the day before (SOS-P1-25).
// Rescheduled asks for the new date and time. The parent reads the list again on "changed".
const props = defineProps({
	visit: { type: Object, required: true },
	confirmations: { type: Array, default: () => [] },
});
const emit = defineEmits(["changed"]);
const rescheduling = ref(false);
const when = ref("");
const error = ref("");

function choose(status) {
	error.value = "";
	if (status === "Rescheduled") {
		rescheduling.value = true;
		when.value = "";
		return;
	}
	rescheduling.value = false;
	save(status, null);
}

function cancelReschedule() {
	rescheduling.value = false;
	emit("changed"); // put the box back on the saved status
}

async function save(status, datetime) {
	error.value = "";
	try {
		await crmApi.confirmSiteVisit(props.visit.name, status, datetime);
		rescheduling.value = false;
	} catch (e) {
		error.value = serverMessage(e, "The confirmation could not be saved.");
	}
	emit("changed");
}
</script>
