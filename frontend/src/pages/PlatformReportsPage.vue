<template>
	<div data-testid="sellos-platform-reports-page">
		<PageHeader
			title="Platform reports"
			text="Companies, usage and calling spend as totals for each company. These reports hold no lead, client or call record and no phone number."
			icon="lucide-chart-column"
		/>
		<div v-if="error" data-testid="sellos-platform-reports-error">
			<LoadError :message="error" @retry="start" />
		</div>
		<LoadingSkeleton v-else-if="!reports" />
		<template v-else>
			<FilterBar
				apply-label="Show report"
				clear-label="Last 30 days"
				@apply="load"
				@clear="reset"
			>
				<FormField
					v-model="key"
					type="select"
					label="Report"
					:options="reports.map((r) => ({ label: r.title, value: r.key }))"
					data-testid="sellos-platform-reports-report"
				/>
				<FormField
					v-if="dated"
					v-model="range.from_date"
					type="date"
					label="From"
					data-testid="sellos-platform-reports-from"
				/>
				<FormField
					v-if="dated"
					v-model="range.to_date"
					type="date"
					label="To"
					data-testid="sellos-platform-reports-to"
				/>
			</FilterBar>
			<LoadingSkeleton v-if="!result" />
			<template v-else>
				<p
					class="mb-ui-md text-sm text-ink-muted"
					data-testid="sellos-platform-reports-about"
				>
					{{ result.report.description }}
					<span v-if="result.report.dated" data-testid="sellos-platform-reports-months">
						Months from {{ result.first_month.slice(0, 7) }} to
						{{ result.last_month.slice(0, 7) }}; a month with any day in the dates
						counts in full.
					</span>
				</p>
				<div class="mb-ui-md grid grid-cols-2 gap-ui-md md:grid-cols-3">
					<StatCard
						v-for="stat in result.stats"
						:key="stat.label"
						:label="stat.label"
						:value="statText(stat)"
						:data-stat="stat.label"
						value-testid="sellos-platform-reports-stat"
					/>
				</div>
				<ListCard :title="result.report.title" class="mb-ui-md">
					<EmptyState
						v-if="!result.rows.length"
						title="No companies yet"
						text="No company has been requested yet."
						icon="lucide-building-2"
					/>
					<ReportTable v-else :columns="result.columns" :rows="result.rows" />
				</ListCard>
				<ReportPanels :panels="result.panels" />
			</template>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";

import EmptyState from "../components/EmptyState.vue";
import FilterBar from "../components/FilterBar.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import ReportPanels from "../components/ReportPanels.vue";
import ReportTable from "../components/ReportTable.vue";
import StatCard from "../components/StatCard.vue";
import { serverMessage } from "../crm/crmApi";
import { rupees } from "../reports/callsApi";
import { platformReportApi } from "../reports/portalApi";

const reports = ref(null);
const key = ref("");
const range = reactive({ from_date: "", to_date: "" });
const result = ref(null);
const error = ref("");

const dated = computed(() => reports.value?.find((r) => r.key === key.value)?.dated);

const statText = (stat) =>
	stat.unit === "rupees" ? rupees(stat.value) : Number(stat.value || 0).toLocaleString("en-IN");

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
		range.from_date = result.value.from_date;
		range.to_date = result.value.to_date;
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
