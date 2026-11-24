<template>
	<ul class="space-y-ui-sm" data-testid="sellos-dash-stage-list">
		<li
			v-for="column in columns"
			:key="column.stage"
			class="grid grid-cols-[minmax(0,9rem)_1fr_2.5rem] items-center gap-ui-sm text-sm sm:grid-cols-[minmax(0,12rem)_1fr_3rem]"
			data-testid="sellos-dash-stage"
			:data-stage="column.stage"
		>
			<span class="truncate text-ink-body">{{ column.label }}</span>
			<span class="h-2.5 overflow-hidden rounded-pill bg-surface-subtle" aria-hidden="true">
				<span
					class="block h-full rounded-pill bg-brand"
					:style="{ width: width(column.count) }"
				/>
			</span>
			<b class="text-right tabular-nums text-ink" data-testid="sellos-dash-stage-count">{{
				column.count
			}}</b>
		</li>
	</ul>
</template>

<script setup>
// Leads by stage: one row per pipeline stage, a bar in the brand colour sized against the biggest stage,
// and the count. Pure display; the counts come from get_board.
import { computed } from "vue";

const props = defineProps({ columns: { type: Array, required: true } });

const most = computed(() => Math.max(1, ...props.columns.map((c) => c.count)));
const width = (count) =>
	count ? `${Math.max(4, Math.round((count / most.value) * 100))}%` : "0%";
</script>
