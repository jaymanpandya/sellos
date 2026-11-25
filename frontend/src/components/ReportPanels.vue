<template>
	<div class="grid gap-ui-md" data-testid="sellos-report-panels">
		<div
			v-for="panel in panels"
			:key="panel.key"
			data-testid="sellos-report-panel"
			:data-panel="panel.key"
			:data-available="panel.available ? 'yes' : 'no'"
		>
			<SectionCard v-if="!panel.available" :title="panel.title">
				<EmptyState title="Not live yet" :text="panel.message" icon="lucide-hourglass" />
			</SectionCard>
			<SectionCard v-else :title="panel.title" :help="panel.description">
				<KpiStrip
					v-if="panel.stats?.length"
					:items="
						panel.stats.map((stat) => ({ label: stat.label, value: statText(stat) }))
					"
				/>
				<ReportTable
					:columns="panel.columns"
					:rows="panel.rows || []"
					:first-label="firstLabel"
				/>
			</SectionCard>
		</div>
	</div>
</template>

<script setup>
// The panels of a report that wait for data another task builds: deals and commission statements for a
// partner, revenue, churn and failed payments for the Platform Admin (SOS-P5-03). A panel with no data
// source yet says so; a live one shows its figures on the shared DataTable.
import { rupees, talkTime } from "../reports/callsApi";
import EmptyState from "./EmptyState.vue";
import KpiStrip from "./KpiStrip.vue";
import SectionCard from "./SectionCard.vue";
import ReportTable from "./ReportTable.vue";

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
