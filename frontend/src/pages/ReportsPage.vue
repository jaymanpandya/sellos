<template>
	<div data-testid="sellos-reports-page">
		<PageHeader
			title="Reports"
			text="Choose a report and the dates. Every figure opens the records behind it. You see the records you may see."
			icon="lucide-chart-column"
		/>
		<div v-if="error" data-testid="sellos-reports-error">
			<LoadError :message="error" @retry="start" />
		</div>
		<LoadingSkeleton v-else-if="!reports" />
		<EmptyState
			v-else-if="!reports.length"
			title="No reports for you"
			text="No report has been made visible to your role."
			icon="lucide-chart-column"
		/>
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
					data-testid="sellos-reports-report"
				/>
				<FormField
					v-model="range.from_date"
					type="date"
					label="From"
					data-testid="sellos-reports-from"
				/>
				<FormField
					v-model="range.to_date"
					type="date"
					label="To"
					data-testid="sellos-reports-to"
				/>
			</FilterBar>
			<LoadingSkeleton v-if="!result" />
			<template v-else>
				<p class="mb-ui-xs text-sm text-ink-muted" data-testid="sellos-reports-about">
					{{ result.report.description }} {{ result.report.date_label }} from
					{{ result.from_date }} to {{ result.to_date }}.
				</p>
				<p class="mb-ui-md text-sm text-ink-muted" data-testid="sellos-reports-scope">
					{{ scopeText }}
					<span
						v-if="result.report.last_refreshed"
						data-testid="sellos-reports-refreshed"
					>
						Summary table refreshed {{ result.report.last_refreshed.slice(0, 16) }}.
					</span>
					<AppButton
						v-if="canRefresh"
						class="ml-ui-sm"
						data-testid="sellos-reports-refresh"
						@click="refresh"
					>
						Refresh summary table
					</AppButton>
				</p>
				<div class="mb-ui-md grid grid-cols-2 gap-ui-md md:grid-cols-3">
					<div>
						<StatCard
							:label="result.report.measure_label"
							:value="show(result.report.unit, grand)"
							:note="`${result.totals.count} records`"
							icon="lucide-sigma"
							value-testid="sellos-reports-total"
						/>
						<AppButton
							class="mt-ui-sm w-full"
							data-testid="sellos-reports-open-all"
							@click="open('All records', undefined)"
						>
							See records
						</AppButton>
					</div>
				</div>
				<ListCard
					:title="`By ${result.report.group_label.toLowerCase()}`"
					class="mb-ui-md"
				>
					<EmptyState
						v-if="!result.rows.length"
						title="Nothing in these dates"
						text="No record falls between these dates. Choose other dates."
						icon="lucide-chart-column"
					/>
					<table
						v-else
						class="w-full text-left text-sm"
						data-testid="sellos-reports-rows"
					>
						<thead class="text-xs text-ink-muted">
							<tr>
								<th scope="col" class="py-ui-sm">
									{{ result.report.group_label }}
								</th>
								<th scope="col">Records</th>
								<th v-if="isSum" scope="col">{{ result.report.measure_label }}</th>
								<th scope="col"><span class="sr-only">Records</span></th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							<tr
								v-for="row in result.rows"
								:key="row.group"
								data-testid="sellos-reports-row"
								:data-group="row.group"
								class="text-ink"
							>
								<td class="py-ui-sm">{{ row.label }}</td>
								<td class="tabular-nums" data-col="count">{{ row.count }}</td>
								<td v-if="isSum" class="tabular-nums" data-col="total">
									{{ show(result.report.unit, row.total) }}
								</td>
								<td>
									<AppButton
										data-testid="sellos-reports-open"
										@click="open(row.label, row.group)"
									>
										Records
									</AppButton>
								</td>
							</tr>
						</tbody>
					</table>
				</ListCard>
				<ListCard v-if="drill" :title="drill.title" class="mb-ui-md">
					<div data-testid="sellos-reports-drill" :data-count="drill.total">
						<p
							class="mb-ui-sm text-sm text-ink-muted"
							data-testid="sellos-reports-drill-total"
						>
							{{ drill.total }} records<span v-if="drill.truncated">
								, the newest {{ drill.shown }} are listed</span
							>.
						</p>
						<EmptyState
							v-if="!drill.records.length"
							title="No records"
							text="No record matches this figure."
							icon="lucide-file-search"
						/>
						<table v-else class="w-full text-left text-sm">
							<thead class="text-xs text-ink-muted">
								<tr>
									<th
										v-for="(column, at) in drill.columns"
										:key="column.field"
										scope="col"
										:class="at === 0 ? 'py-ui-sm' : ''"
									>
										{{ column.label }}
									</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-line-soft">
								<tr
									v-for="record in drill.records"
									:key="record.name"
									data-testid="sellos-reports-record"
									:data-record="record.name"
									class="text-ink"
								>
									<td
										v-for="(column, at) in drill.columns"
										:key="column.field"
										:class="at === 0 ? 'py-ui-sm' : ''"
									>
										<router-link
											v-if="column.field === leadColumn && record.lead"
											class="text-brand underline"
											:to="`/crm/leads/${record.lead}`"
										>
											{{ cell(column.field, record.values[at]) }}
										</router-link>
										<span v-else>{{
											cell(column.field, record.values[at])
										}}</span>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</ListCard>
			</template>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import FilterBar from "../components/FilterBar.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import StatCard from "../components/StatCard.vue";
import { serverMessage } from "../crm/crmApi";
import { rupees, talkTime } from "../reports/callsApi";
import { reportsApi } from "../reports/engineApi";

const reports = ref(null);
const scope = ref("own");
const key = ref("");
const range = reactive({ from_date: "", to_date: "" });
const result = ref(null);
const drill = ref(null);
const error = ref("");

const isSum = computed(() => result.value?.report.measure === "Sum");
const grand = computed(() =>
	isSum.value ? result.value.totals.total : result.value.totals.count
);
const canRefresh = computed(() => scope.value === "all");
const scopeText = computed(
	() =>
		({
			all: "All records of the company.",
			team: "Your team's records only.",
			own: "Your own records only.",
		}[scope.value] || "")
);
// The column that holds the lead's name opens the lead.
const leadColumn = computed(
	() => drill.value?.columns.find((c) => ["lead", "lead_title"].includes(c.field))?.field
);

function show(unit, value) {
	if (unit === "rupees") return rupees(value);
	if (unit === "seconds") return talkTime(value);
	return Number(value || 0).toLocaleString("en-IN");
}

function cell(field, value) {
	if (field === "cost_rupees") return rupees(value);
	if (field === "duration") return talkTime(value);
	if (typeof value === "string" && /^\d{4}-\d\d-\d\d \d\d:\d\d/.test(value))
		return value.slice(0, 16);
	return value ?? "";
}

async function start() {
	error.value = "";
	try {
		const found = await reportsApi.list();
		scope.value = found.scope;
		reports.value = found.reports.filter((r) => r.enabled);
		if (reports.value.length) key.value = reports.value[0].key;
	} catch (e) {
		error.value = serverMessage(e, "The reports could not be loaded.");
	}
}

async function load() {
	if (!key.value) return;
	error.value = "";
	drill.value = null;
	try {
		result.value = await reportsApi.run(key.value, { ...range });
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

// The records behind a figure, for the dates the report shows (not for dates typed since).
async function open(title, group) {
	try {
		const found = await reportsApi.records(
			result.value.report.key,
			{ from_date: result.value.from_date, to_date: result.value.to_date },
			group
		);
		drill.value = { title, ...found };
	} catch (e) {
		error.value = serverMessage(e, "The records could not be loaded.");
	}
}

async function refresh() {
	try {
		await reportsApi.refresh(result.value.report.key);
		await load();
	} catch (e) {
		error.value = serverMessage(e, "The summary table could not be refreshed.");
	}
}

watch(key, () => {
	result.value = null;
	load();
});
onMounted(start);
</script>
