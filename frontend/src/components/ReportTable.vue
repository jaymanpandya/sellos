<template>
	<DataTable
		:title="title"
		:columns="tableColumns"
		:rows="tableRows"
		row-key="key"
		:row-attrs="rowAttrs"
		:page-size="200"
		:empty-title="emptyTitle"
		:empty-text="emptyText"
		empty-icon="lucide-chart-column"
		testid="sellos-report-table"
		row-testid="sellos-report-row"
		empty-testid="sellos-report-table-empty"
	>
		<template v-for="column in columns" :key="column.field" #[slotName(column)]="{ row }">
			<span class="tabular-nums" :data-col="column.field">{{
				show(column.unit, row[fieldKey(column)])
			}}</span>
		</template>
	</DataTable>
</template>

<script setup>
// A table of figures, one row for each thing and one column for each figure, with a unit for each column
// (SOS-P5-03), on the shared DataTable. The Platform Admin's totals per company and a billing panel's rows
// use it. Every row keeps data-key and every figure data-col, which the specs read.
import { computed } from "vue";

import { rupees, talkTime } from "../reports/callsApi";
import DataTable from "./DataTable.vue";

const props = defineProps({
	columns: { type: Array, required: true },
	rows: { type: Array, required: true },
	firstLabel: { type: String, default: "Company" },
	title: { type: String, default: "" },
	emptyTitle: { type: String, default: "Nothing in these dates" },
	emptyText: { type: String, default: "No record falls between these dates." },
});

const fieldKey = (column) => `f_${column.field}`;
const slotName = (column) => `cell-${fieldKey(column)}`;
const rowAttrs = (row) => ({ "data-key": row.key });

const tableColumns = computed(() => [
	{ key: "label", label: props.firstLabel, primary: true },
	...props.columns.map((c) => ({
		key: fieldKey(c),
		label: c.label,
		align: c.unit === "text" ? "left" : "right",
	})),
]);
const tableRows = computed(() =>
	props.rows.map((row) => ({
		key: row.key,
		label: row.label,
		...Object.fromEntries(props.columns.map((c, at) => [fieldKey(c), row.values[at]])),
	}))
);

function show(unit, value) {
	if (unit === "rupees") return rupees(value);
	if (unit === "seconds") return talkTime(value);
	if (unit === "text") return value ?? "";
	return Number(value || 0).toLocaleString("en-IN");
}
</script>
