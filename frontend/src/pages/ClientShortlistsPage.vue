<template>
	<PageTemplate data-testid="sellos-client-shortlists-page">
		<template #header>
			<PageHeader
				title="Your shortlists"
				text="Homes your agent has chosen for you."
				icon="lucide-list-checks"
			/>
		</template>
		<template v-if="loaded && !loadError" #kpis>
			<KpiStrip
				:items="[
					{
						label: 'Shortlists',
						value: rows.length,
						caption: 'Shared with you',
						icon: 'lucide-list-checks',
					},
					{
						label: 'Homes',
						value: totalHomes,
						caption: 'Across all shortlists',
						icon: 'lucide-house',
					},
				]"
				data-testid="sellos-client-shortlists-stats"
			/>
		</template>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-client-shortlists-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<DataTable
			title="Shortlists"
			:columns="columns"
			:rows="rows"
			:loading="!loaded"
			empty-title="No shortlist has been shared with you yet"
			empty-text="Your agent will share homes with you here."
			empty-icon="lucide-list-checks"
			testid="sellos-client-shortlists-table"
			row-testid="sellos-client-shortlist-row"
			empty-testid="sellos-client-shortlists-empty"
		>
			<template #cell-title="{ row }">
				<router-link
					:to="`/client/shortlists/${encodeURIComponent(row.name)}`"
					class="ui-link ui-text-strong"
					data-testid="sellos-client-shortlist-link"
				>
					{{ row.title }}
				</router-link>
			</template>
			<template #cell-item_count="{ row }">{{ row.item_count }} homes</template>
			<template #cell-shared_on="{ row }">{{ formatWhen(row.shared_on) }}</template>
		</DataTable>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import DataTable from "../components/DataTable.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import { serverMessage } from "../crm/crmApi";
import { formatWhen } from "../format";
import { shortlistApi } from "../inventory/inventoryApi";

// The client's own shortlists, the ones shared with them (SOS-P7-09).
const rows = ref([]);
const loaded = ref(false);
const loadError = ref("");
const columns = [
	{ key: "title", label: "Shortlist", primary: true },
	{ key: "item_count", label: "Homes" },
	{ key: "agent_name", label: "From" },
	{ key: "shared_on", label: "Shared" },
];
const totalHomes = computed(() => rows.value.reduce((n, r) => n + Number(r.item_count || 0), 0));

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
