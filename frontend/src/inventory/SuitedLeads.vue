<template>
	<div class="mt-ui-md" data-testid="sellos-suited-leads">
		<AppButton type="button" data-testid="sellos-suited-load" @click="load">
			Leads this suits
		</AppButton>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-suited-error"
			class="mt-ui-sm text-sm text-accent"
		>
			{{ error }}
		</p>
		<template v-if="result">
			<p
				v-if="!result.eligible"
				class="mt-ui-sm text-sm text-ink-muted"
				data-testid="sellos-suited-ineligible"
			>
				{{ result.message }}
			</p>
			<EmptyState
				v-else-if="!result.leads.length"
				title="No leads suit this"
				text="None of the leads you may see want something like it."
				icon="lucide-users"
			/>
			<ul class="mt-ui-sm space-y-ui-sm">
				<li
					v-for="l in result.leads"
					:key="l.name"
					class="rounded border border-line-soft p-ui-md"
					data-testid="sellos-suited-lead"
					:data-lead="l.name"
					:data-score="l.score"
				>
					<div class="flex flex-wrap items-center gap-3">
						<router-link
							:to="`/crm/leads/${encodeURIComponent(l.name)}`"
							class="ui-link font-medium"
						>
							{{ l.client_name || l.lead_title || l.name }}
						</router-link>
						<StatusBadge :tone="scoreTone(l.score)" :label="`${l.score} out of 100`" />
						<span class="text-sm text-ink-muted" data-testid="sellos-suited-phone">{{
							l.phone
						}}</span>
						<span class="text-sm text-ink-muted">{{ l.assigned_to_name }}</span>
					</div>
					<MatchParts :parts="l.parts" />
				</li>
			</ul>
		</template>
	</div>
</template>

<script setup>
import { ref, watch } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import MatchParts from "./MatchParts.vue";
import { matchApi, scoreTone } from "./inventoryApi";

// The leads a unit or a listing suits among the leads the user may see, with masked phone numbers (SOS-P7-08).
const props = defineProps({
	kind: { type: String, required: true }, // "unit" or "listing"
	name: { type: String, required: true },
});
const result = ref(null);
const error = ref("");

watch(
	() => props.name,
	() => {
		result.value = null;
		error.value = "";
	}
);

async function load() {
	error.value = "";
	try {
		result.value =
			props.kind === "unit"
				? await matchApi.forUnit(props.name)
				: await matchApi.forListing(props.name);
	} catch (e) {
		error.value = serverMessage(e, "The leads could not be loaded.");
	}
}
</script>
