<template>
	<div v-if="weights" class="ui-card mt-ui-md" data-testid="sellos-match-weights">
		<h2 class="ui-card-heading mb-ui-sm">Match score weights</h2>
		<p class="mb-ui-md text-sm text-ink-muted">
			How much each part counts when SellOS scores a home for a buyer. 25 each by default.
		</p>
		<div class="flex flex-wrap items-end gap-ui-sm">
			<FormField
				v-for="p in parts"
				:key="p.key"
				v-model="weights[p.key]"
				type="number"
				:label="p.label"
				class="w-40"
				:data-testid="`sellos-match-weight-${p.key}`"
			/>
			<AppButton type="button" data-testid="sellos-match-weights-save" @click="save">
				Save weights
			</AppButton>
		</div>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-match-weights-error"
			class="mt-ui-sm text-sm text-accent"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-match-weights-notice"
			class="mt-ui-sm text-sm text-ink"
		>
			{{ notice }}
		</p>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import FormField from "../components/FormField.vue";
import { serverMessage } from "../crm/crmApi";
import { session } from "../session";
import { matchApi } from "./inventoryApi";

// The four weights of the match score. Only a Company Admin sees and saves them (SOS-P7-08).
const parts = [
	{ key: "budget", label: "Budget" },
	{ key: "configuration", label: "Configuration" },
	{ key: "locality", label: "Locality" },
	{ key: "property_type", label: "Property type" },
];
const weights = ref(null);
const error = ref("");
const notice = ref("");

onMounted(async () => {
	if (!session.roles.includes("SellOS Company Admin")) return;
	try {
		weights.value = reactive({ ...(await matchApi.settings()).weights });
	} catch (e) {
		error.value = serverMessage(e, "The weights could not be loaded.");
	}
});

async function save() {
	error.value = "";
	notice.value = "";
	try {
		weights.value = reactive({ ...(await matchApi.saveSettings(weights.value)).weights });
		notice.value = "The weights are saved.";
	} catch (e) {
		error.value = serverMessage(e, "The weights could not be saved.");
	}
}
</script>
