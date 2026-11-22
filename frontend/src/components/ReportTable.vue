<template>
	<table class="w-full text-left text-sm" data-testid="sellos-report-table">
		<thead class="text-xs text-ink-muted">
			<tr>
				<th scope="col" class="py-ui-sm">{{ firstLabel }}</th>
				<th v-for="column in columns" :key="column.field" scope="col">
					{{ column.label }}
				</th>
			</tr>
		</thead>
		<tbody class="divide-y divide-line-soft">
			<tr
				v-for="row in rows"
				:key="row.key"
				data-testid="sellos-report-row"
				:data-key="row.key"
				class="text-ink"
			>
				<td class="py-ui-sm">{{ row.label }}</td>
				<td
					v-for="(column, at) in columns"
					:key="column.field"
					class="tabular-nums"
					:data-col="column.field"
				>
					{{ show(column.unit, row.values[at]) }}
				</td>
			</tr>
		</tbody>
	</table>
</template>

<script setup>
// A table of figures, one row for each thing and one column for each figure, with a unit for each column
// (SOS-P5-03). The Platform Admin's totals per company and a billing panel's rows use it.
import { rupees, talkTime } from "../reports/callsApi";

defineProps({
	columns: { type: Array, required: true },
	rows: { type: Array, required: true },
	firstLabel: { type: String, default: "Company" },
});

function show(unit, value) {
	if (unit === "rupees") return rupees(value);
	if (unit === "seconds") return talkTime(value);
	if (unit === "text") return value ?? "";
	return Number(value || 0).toLocaleString("en-IN");
}
</script>
