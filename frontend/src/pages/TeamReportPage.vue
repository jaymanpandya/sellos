<template>
	<PageTemplate data-testid="sellos-teamreport-page">
		<template #header>
			<PageHeader
				title="Team report"
				text="The open leads of your team, by agent and by stage. Only your own team is counted."
				icon="lucide-chart-column"
			/>
		</template>

		<template v-if="report" #kpis>
			<KpiStrip :items="kpis" />
		</template>

		<div v-if="error" data-testid="sellos-teamreport-error">
			<LoadError :message="error" @retry="load" />
		</div>
		<LoadingSkeleton v-else-if="!report" />
		<template v-else>
			<ListCard title="Your team" class="mb-ui-md">
				<p class="text-ink" data-testid="sellos-teamreport-total">
					Leads: {{ report.total }}
				</p>
				<p class="text-sm text-ink-muted" data-testid="sellos-teamreport-teams">
					Teams: {{ report.teams.join(", ") || "None" }}
				</p>
			</ListCard>
			<div class="grid grid-cols-1 gap-ui-md lg:grid-cols-2">
				<DataTable
					title="By agent"
					caption="Open leads by agent"
					:columns="agentColumns"
					:rows="report.by_agent"
					row-key="agent"
					empty-title="No open leads"
					empty-text="No agent in your team has an open lead."
					empty-icon="lucide-user"
					testid="sellos-teamreport-agents"
					row-testid="sellos-teamreport-agent"
				>
					<template #cell-leads="{ row }">
						<span class="tabular-nums">{{ row.leads }}</span>
					</template>
				</DataTable>
				<DataTable
					title="By stage"
					caption="Open leads by stage"
					:columns="stageColumns"
					:rows="stageRows"
					row-key="key"
					empty-title="No open leads"
					empty-text="There are no open leads in any stage."
					empty-icon="lucide-layers"
					testid="sellos-teamreport-stages"
					row-testid="sellos-teamreport-stage"
				>
					<template #cell-leads="{ row }">
						<span class="tabular-nums">{{ row.leads }}</span>
					</template>
				</DataTable>
			</div>
		</template>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import DataTable from "../components/DataTable.vue";
import KpiStrip from "../components/KpiStrip.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import { teamsApi } from "../company/teamsApi";
import { serverMessage } from "../crm/crmApi";

const report = ref(null);
const error = ref("");

const kpis = computed(() => [
	{
		label: "Open leads",
		value: report.value.total,
		caption: "in your team",
		icon: "lucide-users",
	},
	{
		label: "Agents",
		value: report.value.by_agent.length,
		caption: "in the report below",
		icon: "lucide-user",
	},
	{
		label: "Stages in use",
		value: report.value.by_stage.length,
		caption: "holding open leads",
		icon: "lucide-layers",
	},
]);
const agentColumns = [
	{ key: "agent_name", label: "Agent", primary: true, sortable: true },
	{ key: "leads", label: "Open leads", sortable: true, align: "right" },
];
const stageColumns = [
	{ key: "stage", label: "Stage", primary: true, sortable: true },
	{ key: "leads", label: "Open leads", sortable: true, align: "right" },
];
const stageRows = computed(() =>
	(report.value?.by_stage || []).map((row, i) => ({
		key: `${i}`,
		stage: row.stage || "No stage",
		leads: row.leads,
	}))
);

async function load() {
	error.value = "";
	try {
		report.value = await teamsApi.report();
	} catch (e) {
		error.value = serverMessage(e, "The report could not be loaded.");
	}
}

onMounted(load);
</script>
