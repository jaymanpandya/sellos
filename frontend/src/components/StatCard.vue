<template>
	<div
		class="rounded-card border border-line bg-surface p-ui-md shadow-card"
		:data-tone="tone || 'neutral'"
	>
		<div class="flex items-start justify-between gap-ui-sm">
			<span class="block text-xs font-medium text-ink-muted">{{ label }}</span>
			<span
				v-if="icon"
				class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-round"
				:style="chipStyle"
				aria-hidden="true"
			>
				<span :class="icon" class="icon-inherit size-4" />
			</span>
		</div>
		<b class="my-1 block text-stat tabular-nums" :data-testid="valueTestid">{{ value }}</b>
		<span v-if="note" class="block text-xs text-ink-muted">{{ note }}</span>
	</div>
</template>

<script setup>
// PAMAA's StatCard (SOS-UI-2B), without the count-up animation and the area colours: a label, a
// number and a note. `tone` tints the chip in a status colour.
import { computed } from "vue";

import { status } from "../theme/ui-tokens.js";

const props = defineProps({
	label: { type: String, required: true },
	value: { type: [String, Number], required: true },
	note: { type: String, default: "" },
	icon: { type: String, default: "" },
	tone: { type: String, default: "" },
	// The test id of the number, when a spec reads it on its own.
	valueTestid: { type: String, default: "sellos-stat-value" },
});

const chipStyle = computed(() => {
	const colours = status[props.tone];
	return colours
		? { backgroundColor: colours.bg, color: colours.ink }
		: { backgroundColor: "var(--ui-brand-soft)", color: "var(--sos-brand)" };
});
</script>
