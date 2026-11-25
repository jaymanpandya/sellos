<template>
	<PageTemplate data-testid="sellos-platform-reports-page">
		<template #header>
			<PageHeader
				title="Platform reports"
				text="Companies, usage and calling spend as totals for each company. These reports hold no lead, client or call record and no phone number."
				icon="lucide-chart-column"
			/>
		</template>

		<template v-if="result && !error" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-platform-reports-stats" />
		</template>

		<template v-if="reports && !error" #filters>
			<FilterBar
				v-model:open="moreOpen"
				hide-search
				apply-label="Show report"
				clear-label="Last 30 days"
				more-testid="sellos-platform-reports-filters-toggle"
				:active="datesChanged"
				data-testid="sellos-platform-reports-filters"
				@apply="load"
				@clear="reset"
			>
				<FormField
					v-model="key"
					compact
					type="select"
					label="Report"
					:options="reports.map((r) => ({ label: r.title, value: r.key }))"
					data-testid="sellos-platform-reports-report"
				/>
				<template v-if="dated" #more>
					<FormField
						v-model="range.from_date"
						type="date"
						label="From"
						data-testid="sellos-platform-reports-from"
					/>
					<FormField
						v-model="range.to_date"
						type="date"
						label="To"
						data-testid="sellos-platform-reports-to"
					/>
				</template>
			</FilterBar>
		</template>

		<div v-if="error" data-testid="sellos-platform-reports-error">
			<LoadError :message="error" @retry="start" />
		</div>
		<LoadingSkeleton v-else-if="!reports || !result" />
		<div v-else class="space-y-ui-md">
			<p class="ui-text-muted" data-testid="sellos-platform-reports-about">
				{{ result.report.description }}
				<span v-if="result.report.dated" data-testid="sellos-platform-reports-months">
					Months from {{ result.first_month.slice(0, 7) }} to
					{{ result.last_month.slice(0, 7) }}; a month with any day in the dates counts
					in full.
				</span>
			</p>
			<ReportTable
				:title="result.report.title"
				:columns="result.columns"
				:rows="result.rows"
				empty-title="No companies yet"
				empty-text="No company has been requested yet."
			/>
			<ReportPanels :panels="result.panels" />
		</div>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";

import FilterBar from "../components/FilterBar.vue";
import FormField from "../components/FormField.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import ReportPanels from "../components/ReportPanels.vue";
import ReportTable from "../components/ReportTable.vue";
import { serverMessage } from "../crm/crmApi";
import { rupees } from "../reports/callsApi";
import { platformReportApi } from "../reports/portalApi";

const reports = ref(null);
const key = ref("");
const range = reactive({ from_date: "", to_date: "" });
const result = ref(null);
const error = ref("");
// The dates are the one filter here, so the panel that holds them starts open.
const moreOpen = ref(true);
// The dates the report opened with, so Clear shows only when they have been changed.
const defaults = reactive({ from_date: "", to_date: "" });
const datesChanged = computed(
	() =>
		Boolean(dated.value) &&
		Boolean(defaults.from_date) &&
		(range.from_date !== defaults.from_date || range.to_date !== defaults.to_date)
);

const dated = computed(() => reports.value?.find((r) => r.key === key.value)?.dated);

// The server's own figures, in its own order; the strip shows the first four.
const statText = (stat) =>
	stat.unit === "rupees" ? rupees(stat.value) : Number(stat.value || 0).toLocaleString("en-IN");
const kpis = computed(() =>
	result.value.stats.map((stat) => ({
		label: stat.label,
		value: statText(stat),
		valueTestid: "sellos-platform-reports-stat",
		attrs: { "data-stat": stat.label },
	}))
);

async function start() {
	error.value = "";
	try {
		reports.value = (await platformReportApi.list()).reports;
		if (reports.value.length) key.value = reports.value[0].key;
	} catch (e) {
		error.value = serverMessage(e, "The reports could not be loaded.");
	}
}

async function load() {
	if (!key.value) return;
	error.value = "";
	try {
		result.value = await platformReportApi.run(key.value, dated.value ? { ...range } : {});
		const fresh = !range.from_date && !range.to_date;
		range.from_date = result.value.from_date;
		range.to_date = result.value.to_date;
		if (fresh || !defaults.from_date) {
			defaults.from_date = range.from_date;
			defaults.to_date = range.to_date;
		}
	} catch (e) {
		error.value = serverMessage(e, "The report could not be loaded.");
	}
}

function reset() {
	range.from_date = "";
	range.to_date = "";
	load();
}

watch(key, () => {
	result.value = null;
	load();
});
onMounted(start);
</script>
