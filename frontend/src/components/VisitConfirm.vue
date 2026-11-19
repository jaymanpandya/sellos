<template>
	<div class="flex flex-wrap items-center gap-2" data-testid="sellos-visit-confirm">
		<select
			:value="visit.confirmation_status"
			aria-label="Confirmation"
			data-testid="sellos-visit-confirm-status"
			class="field w-auto"
			:disabled="visit.status === 'Done'"
			@change="choose($event.target.value)"
		>
			<option v-for="c in confirmations" :key="c" :value="c">{{ c }}</option>
		</select>
		<form
			v-if="rescheduling"
			class="flex flex-wrap items-center gap-2"
			data-testid="sellos-visit-reschedule-form"
			@submit.prevent="save('Rescheduled', when)"
		>
			<input
				v-model="when"
				required
				type="datetime-local"
				aria-label="New date and time"
				data-testid="sellos-visit-reschedule-when"
				class="field w-auto"
			/>
			<button type="submit" class="btn" data-testid="sellos-visit-reschedule-save">
				Reschedule
			</button>
			<button type="button" class="btn" @click="cancelReschedule">Cancel</button>
		</form>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-visit-confirm-error"
			class="text-sm text-accent"
		>
			{{ error }}
		</p>
	</div>
</template>

<script setup>
import { ref } from "vue";

import { crmApi, serverMessage } from "../crm/crmApi";

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
