<template>
	<div data-testid="sellos-client-shortlists-page">
		<PageHeader
			title="Your shortlists"
			text="Homes your agent has chosen for you."
			icon="lucide-list-checks"
		/>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-client-shortlists-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<ListCard title="Shortlists">
			<EmptyState
				v-if="loaded && !loadError && !rows.length"
				title="No shortlist has been shared with you yet"
				text="Your agent will share homes with you here."
				icon="lucide-list-checks"
			/>
			<ul class="space-y-ui-sm">
				<li
					v-for="row in rows"
					:key="row.name"
					class="flex flex-wrap items-center gap-3 rounded-input border border-line-soft p-ui-md"
					data-testid="sellos-client-shortlist-row"
					:data-name="row.name"
				>
					<router-link
						:to="`/client/shortlists/${encodeURIComponent(row.name)}`"
						class="ui-link font-medium"
						data-testid="sellos-client-shortlist-link"
					>
						{{ row.title }}
					</router-link>
					<span class="text-sm text-ink-muted">
						{{ row.item_count }} homes, from {{ row.agent_name }},
						{{ whenText(row.shared_on) }}
					</span>
				</li>
			</ul>
		</ListCard>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue";

import EmptyState from "../components/EmptyState.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import { serverMessage } from "../crm/crmApi";
import { shortlistApi, whenText } from "../inventory/inventoryApi";

// The client's own shortlists, the ones shared with them (SOS-P7-09).
const rows = ref([]);
const loaded = ref(false);
const loadError = ref("");

async function load() {
	loadError.value = "";
	try {
		rows.value = (await shortlistApi.mine()).shortlists;
	} catch (e) {
		loadError.value = serverMessage(e, "Your shortlists could not be loaded.");
	}
	loaded.value = true;
}

onMounted(load);
</script>
