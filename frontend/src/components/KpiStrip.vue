<template>
	<div
		v-if="shown.length"
		class="mb-4 grid grid-cols-2 gap-4"
		:class="shown.length > 2 ? 'md:grid-cols-4' : ''"
		data-testid="sellos-kpi-strip"
	>
		<StatCard
			v-for="item in shown"
			:key="item.label"
			:label="item.label"
			:value="item.value"
			:note="item.caption"
			:icon="item.icon"
			:tone="item.tone"
			:to="item.to"
			v-bind="{
				...(item.valueTestid ? { 'value-testid': item.valueTestid } : {}),
				...(item.attrs || {}),
			}"
		/>
	</div>
</template>

<script setup>
// The KPI strip: at most four cards, each a label, a number and a one line caption. Extra items are
// dropped, so a page cannot grow a second row of cards.
import { computed } from "vue";

import StatCard from "./StatCard.vue";

const props = defineProps({
	// [{ label, value, caption, icon, tone, valueTestid, attrs }, attrs being extra attributes for the card]
	items: { type: Array, default: () => [] },
});
const shown = computed(() => props.items.slice(0, 4));
</script>
