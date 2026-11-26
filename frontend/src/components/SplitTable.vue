<template>
	<div data-testid="sellos-split-card">
		<div class="overflow-x-auto">
			<table class="w-full text-left text-sm" :data-testid="testid">
				<thead>
					<tr class="text-ink-body">
						<th scope="col" class="py-1 pr-4 font-medium">Name</th>
						<th scope="col" class="py-1 pr-4 font-medium">Role</th>
						<th scope="col" class="py-1 pr-4 text-right font-medium">Percent</th>
						<th scope="col" class="py-1 text-right font-medium">Amount</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="(row, n) in rows"
						:key="n"
						:data-testid="rowTestid"
						:data-party="row.party_type"
						class="border-t border-line"
					>
						<td class="py-2 pr-4">{{ row.party }}</td>
						<td class="py-2 pr-4">{{ row.party_type }}</td>
						<td class="py-2 pr-4 text-right tabular-nums">{{ row.percent }}%</td>
						<td class="py-2 text-right tabular-nums">{{ formatMoney(row.amount) }}</td>
					</tr>
				</tbody>
				<tfoot>
					<tr
						class="border-t border-line font-semibold"
						data-testid="sellos-split-total"
					>
						<td class="py-2 pr-4" colspan="2">Total</td>
						<td
							class="py-2 pr-4 text-right tabular-nums"
							:class="total === 100 ? '' : 'text-danger'"
							data-testid="sellos-split-percent"
						>
							{{ total }}%
						</td>
						<td class="py-2 text-right tabular-nums">{{ formatMoney(amount) }}</td>
					</tr>
				</tfoot>
			</table>
		</div>
		<p
			class="mt-2 ui-text-small"
			:class="total === 100 ? 'ui-text-muted' : 'ui-text-error'"
			data-testid="sellos-split-check"
		>
			{{
				total === 100
					? "The shares add up to 100 percent."
					: `The shares add up to ${total} percent, not 100.`
			}}
		</p>
		<div
			class="mt-2 flex h-3 w-full overflow-hidden rounded-full bg-surface-subtle"
			role="img"
			aria-label="Proportion of each share"
			data-testid="sellos-split-bar"
		>
			<span
				v-for="(row, n) in rows"
				:key="n"
				:style="{ width: `${row.percent}%`, opacity: 1 - n * 0.18 }"
				class="block h-full bg-brand"
				:title="`${row.party}: ${row.percent}%`"
			/>
		</div>
	</div>
</template>

<script setup>
// A commission split: a row per party (name, role, percent, amount), a total row that checks to 100 percent
// and a proportion bar. `rows` is [{ party, party_type, percent, amount }]. Amounts are exact (formatMoney).
import { computed } from "vue";

import { formatMoney } from "../format";

const props = defineProps({
	rows: { type: Array, required: true },
	testid: { type: String, default: "sellos-split-table" },
	rowTestid: { type: String, default: "sellos-split-row" },
});
const total = computed(
	() => Math.round(props.rows.reduce((t, r) => t + Number(r.percent), 0) * 100) / 100
);
const amount = computed(() => props.rows.reduce((t, r) => t + Number(r.amount), 0));
</script>
