<template>
	<div data-testid="sellos-partner-reports-page">
		<PageHeader
			title="Your results"
			text="Your own leads, deals and commission statements. You see only what your firm registered."
			icon="lucide-chart-column"
		/>
		<div v-if="error" data-testid="sellos-partner-reports-error">
			<LoadError :message="error" @retry="load" />
		</div>
		<LoadingSkeleton v-else-if="!result" />
		<template v-else>
			<FilterBar
				apply-label="Show report"
				clear-label="Last 30 days"
				@apply="load"
				@clear="reset"
			>
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
			</FilterBar>
			<p class="mb-ui-md text-sm text-ink-muted" data-testid="sellos-partner-reports-about">
				<span v-if="result.firm" data-testid="sellos-partner-reports-firm">
					{{ result.firm.firm_name }}.
				</span>
				Leads created from {{ result.from_date }} to {{ result.to_date }}. Your own records
				only.
			</p>
			<div class="mb-ui-md grid grid-cols-2 gap-ui-md md:grid-cols-3">
				<StatCard
					label="Your leads"
					:value="result.leads.total"
					icon="lucide-users"
					value-testid="sellos-partner-reports-total"
				/>
			</div>
			<ListCard title="Leads by stage" class="mb-ui-md">
				<EmptyState
					v-if="!result.leads.by_stage.length"
					title="Nothing in these dates"
					text="None of your leads was created between these dates. Choose other dates."
					icon="lucide-chart-column"
				/>
				<table
					v-else
					class="w-full text-left text-sm"
					data-testid="sellos-partner-reports-stages"
				>
					<thead class="text-xs text-ink-muted">
						<tr>
							<th scope="col" class="py-ui-sm">Stage</th>
							<th scope="col">Leads</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-line-soft">
						<tr
							v-for="row in result.leads.by_stage"
							:key="row.stage"
							data-testid="sellos-partner-reports-stage"
							:data-stage="row.stage"
							class="text-ink"
						>
							<td class="py-ui-sm">{{ row.label }}</td>
							<td class="tabular-nums" data-col="count">{{ row.count }}</td>
						</tr>
					</tbody>
				</table>
			</ListCard>
			<ListCard title="Your leads" class="mb-ui-md">
				<p
					class="mb-ui-sm text-sm text-ink-muted"
					data-testid="sellos-partner-reports-shown"
				>
					{{ result.leads.shown }} of {{ result.leads.total }} leads are listed.
				</p>
				<ul
					class="divide-y divide-line-soft text-sm"
					data-testid="sellos-partner-reports-leads"
				>
					<li
						v-for="lead in result.leads.records"
						:key="lead.name"
						data-testid="sellos-partner-reports-lead"
						:data-lead="lead.name"
						class="flex flex-wrap justify-between gap-ui-sm py-ui-sm text-ink"
					>
						<span>{{ lead.title }}</span>
						<span class="text-ink-muted">{{ lead.stage }}, {{ lead.created }}</span>
					</li>
				</ul>
			</ListCard>
			<ReportPanels :panels="result.panels" first-label="Record" />
		</template>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import EmptyState from "../components/EmptyState.vue";
import FilterBar from "../components/FilterBar.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import ReportPanels from "../components/ReportPanels.vue";
import StatCard from "../components/StatCard.vue";
import { serverMessage } from "../crm/crmApi";
import { partnerReportApi } from "../reports/portalApi";

const range = reactive({ from_date: "", to_date: "" });
const result = ref(null);
const error = ref("");

async function load() {
	error.value = "";
	try {
		result.value = await partnerReportApi.run({ ...range });
		range.from_date = result.value.from_date;
		range.to_date = result.value.to_date;
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
