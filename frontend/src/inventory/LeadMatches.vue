<template>
	<ListCard title="Matching homes" data-testid="sellos-lead-matches">
		<AppButton type="button" data-testid="sellos-lead-matches-load" @click="load">
			Find matching homes
		</AppButton>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-lead-matches-error"
			class="mt-ui-sm text-sm text-accent"
		>
			{{ error }}
		</p>
		<template v-if="result">
			<p
				v-if="!result.has_requirements"
				class="mt-ui-sm text-sm text-ink-muted"
				data-testid="sellos-lead-matches-none-asked"
			>
				Save what the buyer wants above, and SellOS can score homes against it.
			</p>
			<EmptyState
				v-else-if="!result.matches.length"
				title="No matching homes"
				text="No Available unit or published listing suits this buyer yet."
				icon="lucide-building"
			/>
			<p
				v-else
				class="mt-ui-sm text-sm text-ink-muted"
				data-testid="sellos-lead-matches-count"
			>
				{{ result.matches.length }} of {{ result.total }} matching homes shown, best first.
			</p>
			<ul class="mt-ui-sm space-y-ui-sm">
				<li
					v-for="m in result.matches"
					:key="m.kind + m.name"
					class="rounded-input border border-line-soft p-ui-md"
					data-testid="sellos-lead-match"
					:data-kind="m.kind"
					:data-title="m.title"
					:data-score="m.score"
				>
					<div class="flex flex-wrap items-center gap-3">
						<span class="font-medium text-ink">{{ m.title }}</span>
						<StatusBadge
							:tone="scoreTone(m.score)"
							:label="`${m.score} out of 100`"
							data-testid="sellos-lead-match-score"
						/>
						<StatusBadge tone="info" :label="m.kind" />
						<span class="text-sm text-ink-muted">
							{{ m.price ? rupees(m.price) : "No price yet" }}
						</span>
					</div>
					<MatchParts :parts="m.parts" />
				</li>
			</ul>
		</template>
	</ListCard>
</template>

<script setup>
import { ref } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import ListCard from "../components/ListCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import MatchParts from "./MatchParts.vue";
import { matchApi, rupees, scoreTone } from "./inventoryApi";

// The published listings and Available units that suit a lead, each scored with the reasons (SOS-P7-08).
const props = defineProps({ lead: { type: String, required: true } });
const result = ref(null);
const error = ref("");

async function load() {
	error.value = "";
	try {
		result.value = await matchApi.forLead(props.lead);
	} catch (e) {
		error.value = serverMessage(e, "The matching homes could not be loaded.");
	}
}
</script>
