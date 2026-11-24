<template>
	<PageTemplate data-testid="sellos-partner-reports-page">
		<template #header>
			<PageHeader
				title="Your results"
				text="Your own leads, deals and commission statements. You see only what your firm registered."
				icon="lucide-chart-column"
			/>
		</template>

		<template v-if="result && !error" #kpis>
			<KpiStrip
				:items="[
					{
						label: 'Your leads',
						value: result.leads.total,
						caption: 'Created in these dates',
						icon: 'lucide-users',
						valueTestid: 'sellos-partner-reports-total',
					},
				]"
				data-testid="sellos-partner-reports-stats"
			/>
		</template>

		<template v-if="result && !error" #filters>
			<FilterBar
				v-model:open="moreOpen"
				hide-search
				apply-label="Show report"
				clear-label="Last 30 days"
				more-testid="sellos-partner-reports-filters-toggle"
				:active="datesChanged"
				data-testid="sellos-partner-reports-filters"
				@apply="load"
				@clear="reset"
			>
				<template #more>
					<FormField
						v-model="range.from_date"
						type="date"
						label="From"
						data-testid="sellos-partner-reports-from"
					/>
					<FormField
						v-model="range.to_date"
						type="date"
						label="To"
						data-testid="sellos-partner-reports-to"
					/>
				</template>
			</FilterBar>
		</template>

		<div v-if="error" data-testid="sellos-partner-reports-error">
			<LoadError :message="error" @retry="load" />
		</div>
		<LoadingSkeleton v-else-if="!result" />
		<div v-else class="space-y-ui-md">
			<p class="text-sm text-ink-muted" data-testid="sellos-partner-reports-about">
				<span v-if="result.firm" data-testid="sellos-partner-reports-firm">
					{{ result.firm.firm_name }}.
				</span>
				Leads created from {{ result.from_date }} to {{ result.to_date }}. Your own records
				only.
			</p>

			<DataTable
				title="Leads by stage"
				:columns="stageColumns"
				:rows="result.leads.by_stage"
				row-key="stage"
				:row-attrs="(row) => ({ 'data-stage': row.stage })"
				:page-size="200"
				empty-title="Nothing in these dates"
				empty-text="None of your leads was created between these dates. Choose other dates."
				empty-icon="lucide-chart-column"
				testid="sellos-partner-reports-stages"
				row-testid="sellos-partner-reports-stage"
				empty-testid="sellos-partner-reports-stages-empty"
			>
				<template #cell-count="{ row }">
					<span class="tabular-nums" data-col="count">{{ row.count }}</span>
				</template>
			</DataTable>

			<p class="text-sm text-ink-muted" data-testid="sellos-partner-reports-shown">
				{{ result.leads.shown }} of {{ result.leads.total }} leads are listed.
			</p>
			<DataTable
				title="Your leads"
				:columns="leadColumns"
				:rows="result.leads.records"
				:row-attrs="(row) => ({ 'data-lead': row.name })"
				:page-size="200"
				empty-title="No leads"
				empty-text="None of your leads was created between these dates."
				empty-icon="lucide-users"
				testid="sellos-partner-reports-leads"
				row-testid="sellos-partner-reports-lead"
				empty-testid="sellos-partner-reports-leads-empty"
			>
				<template #cell-created="{ row }">{{ formatWhen(row.created) }}</template>
			</DataTable>

			<ReportPanels :panels="result.panels" first-label="Record" />
		</div>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import DataTable from "../components/DataTable.vue";
import FilterBar from "../components/FilterBar.vue";
import FormField from "../components/FormField.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import ReportPanels from "../components/ReportPanels.vue";
import { serverMessage } from "../crm/crmApi";
import { formatWhen } from "../format";
import { partnerReportApi } from "../reports/portalApi";

const range = reactive({ from_date: "", to_date: "" });
const result = ref(null);
const error = ref("");
// The dates are the one filter here, so the panel that holds them starts open.
const moreOpen = ref(true);
// The dates the report opened with, so Clear shows only when they have been changed.
const defaults = reactive({ from_date: "", to_date: "" });
const datesChanged = computed(
	() =>
		Boolean(defaults.from_date) &&
		(range.from_date !== defaults.from_date || range.to_date !== defaults.to_date)
);

const stageColumns = [
	{ key: "label", label: "Stage", primary: true },
	{ key: "count", label: "Leads", align: "right" },
];
const leadColumns = [
	{ key: "title", label: "Lead", primary: true },
	{ key: "stage", label: "Stage" },
	{ key: "created", label: "Created" },
];

async function load() {
	error.value = "";
	try {
		result.value = await partnerReportApi.run({ ...range });
		const fresh = !range.from_date && !range.to_date;
		range.from_date = result.value.from_date;
		range.to_date = result.value.to_date;
		if (fresh || !defaults.from_date) {
			defaults.from_date = range.from_date;
			defaults.to_date = range.to_date;
		}
	} catch (e) {
		error.value = serverMessage(e, "Your report could not be loaded.");
	}
}

function reset() {
	range.from_date = "";
	range.to_date = "";
	load();
}

onMounted(load);
</script>
