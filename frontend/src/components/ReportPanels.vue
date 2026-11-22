<template>
	<div class="grid gap-ui-md" data-testid="sellos-report-panels">
		<ListCard
			v-for="panel in panels"
			:key="panel.key"
			:title="panel.title"
			data-testid="sellos-report-panel"
			:data-panel="panel.key"
			:data-available="panel.available ? 'yes' : 'no'"
		>
			<EmptyState
				v-if="!panel.available"
				title="Not live yet"
				:text="panel.message"
				icon="lucide-hourglass"
			/>
			<template v-else>
				<p class="mb-ui-sm text-sm text-ink-muted">{{ panel.description }}</p>
				<div
					v-if="panel.stats?.length"
					class="mb-ui-sm grid grid-cols-2 gap-ui-md md:grid-cols-4"
				>
					<StatCard
						v-for="stat in panel.stats"
						:key="stat.label"
						:label="stat.label"
						:value="statText(stat)"
					/>
				</div>
				<EmptyState
					v-if="!panel.rows?.length"
					title="Nothing in these dates"
					text="No record falls between these dates."
					icon="lucide-chart-column"
				/>
				<ReportTable
					v-else
					:columns="panel.columns"
					:rows="panel.rows"
					:first-label="firstLabel"
				/>
			</template>
		</ListCard>
	</div>
</template>

<script setup>
// The panels of a report that wait for data another task builds: deals and commission statements for a
// partner, revenue, churn and failed payments for the Platform Admin (SOS-P5-03). A panel with no data
// source yet says so; a live one shows its figures.
import { rupees, talkTime } from "../reports/callsApi";
import EmptyState from "./EmptyState.vue";
import ListCard from "./ListCard.vue";
import ReportTable from "./ReportTable.vue";
import StatCard from "./StatCard.vue";

defineProps({
	panels: { type: Array, required: true },
	firstLabel: { type: String, default: "Company" },
});

function statText(stat) {
	if (stat.unit === "rupees") return rupees(stat.value);
	if (stat.unit === "seconds") return talkTime(stat.value);
	return Number(stat.value || 0).toLocaleString("en-IN");
}
</script>
