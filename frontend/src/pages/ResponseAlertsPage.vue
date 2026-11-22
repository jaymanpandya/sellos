<template>
	<div class="max-w-3xl" data-testid="sellos-response-alerts-page">
		<PageHeader
			title="Response time alerts"
			text="Set how fast a new lead must get an agent and a first call or activity. A miss alerts the agent, and the Sales Manager if it is still missed after the same time again."
			icon="lucide-timer"
		/>

		<div v-if="loadError" data-testid="sellos-response-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<LoadingSkeleton v-else-if="loading" />

		<form
			v-else
			class="ui-card space-y-ui-md"
			data-testid="sellos-response-form"
			@submit.prevent="save"
		>
			<h2 class="ui-card-heading">Limits</h2>
			<FormField
				v-model="form.unassignedMinutes"
				type="number"
				label="Minutes a new lead may stay unassigned"
				hint="After this many minutes with no agent, the Company Admin is alerted."
				data-testid="sellos-response-unassigned"
			/>
			<FormField
				v-model="form.contactMinutes"
				type="number"
				label="Minutes an assigned lead may wait for a call or activity"
				hint="Counted from the assignment. The agent is alerted, then the Sales Manager of the agent's team (the Company Admin when there is no team)."
				data-testid="sellos-response-contact"
			/>
			<p
				v-if="error"
				data-testid="sellos-response-error"
				role="alert"
				class="text-sm text-accent"
			>
				{{ error }}
			</p>
			<p
				v-if="saved"
				data-testid="sellos-response-saved"
				role="status"
				class="text-sm text-ink"
			>
				Saved.
			</p>
			<AppButton type="submit" variant="primary" data-testid="sellos-response-save">
				Save
			</AppButton>
		</form>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import { logRequestError } from "../api";
import AppButton from "../components/AppButton.vue";
import FormField from "../components/FormField.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import { serverMessage } from "../crm/crmApi";
import { responseTimesApi } from "../crm/responseTimesApi";

const form = reactive({ unassignedMinutes: "", contactMinutes: "" });
const loading = ref(true);
const loadError = ref("");
const error = ref("");
const saved = ref(false);

function apply(limits) {
	form.unassignedMinutes = String(limits.unassigned_minutes);
	form.contactMinutes = String(limits.contact_minutes);
}

async function load() {
	loading.value = true;
	loadError.value = "";
	try {
		apply(await responseTimesApi.get());
	} catch (e) {
		loadError.value = serverMessage(e, "The response time limits could not be loaded.");
		logRequestError("response time limits failed", e);
	} finally {
		loading.value = false;
	}
}

async function save() {
	error.value = "";
	saved.value = false;
	try {
		apply(await responseTimesApi.save(form));
		saved.value = true;
	} catch (e) {
		error.value = serverMessage(e, "The limits could not be saved.");
	}
}

onMounted(load);
</script>
