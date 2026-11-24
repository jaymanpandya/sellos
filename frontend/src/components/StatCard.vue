<template>
	<component
		:is="to ? 'router-link' : 'div'"
		:to="to || undefined"
		class="ui-stat-tile"
		:class="to ? 'is-link' : ''"
		:data-tone="tone || 'neutral'"
		:style="barStyle"
	>
		<span class="ui-stat-bar" aria-hidden="true" />
		<span class="flex items-start justify-between gap-2">
			<span class="ui-text-muted">{{ label }}</span>
			<span v-if="icon" class="ui-icon-chip-sm" :style="chipStyle" aria-hidden="true">
				<span :class="icon" class="icon-inherit size-4" />
			</span>
		</span>
		<b class="ui-stat-number" :data-testid="valueTestid">{{ value }}</b>
		<span v-if="note" class="ui-text-muted block">{{ note }}</span>
	</component>
</template>

<script setup>
// The stat tile (docs/DESIGN_SYSTEM.md): the label top left in muted text, a 32px round area icon chip top right, the
// number under the label (24px, semibold, tabular), an optional helper line, and a 3px bar along the top edge in the
// tile's colour, clipped by the card's corners: the area's accent for normal, amber for waiting or at risk (`warning`),
// red for late (`danger`), green for done (`success`). With `to` the whole tile is the link.
import { computed } from "vue";

import { status } from "../theme/ui-tokens.js";

const props = defineProps({
	label: { type: String, required: true },
	value: { type: [String, Number], required: true },
	note: { type: String, default: "" },
	icon: { type: String, default: "" },
	tone: { type: String, default: "" },
	to: { type: [String, Object], default: null },
	// The test id of the number, when a spec reads it on its own.
	valueTestid: { type: String, default: "sellos-stat-value" },
});

const colours = computed(() => status[props.tone]);
const barStyle = computed(() =>
	colours.value
		? { "--tile-colour": colours.value.ink }
		: { "--tile-colour": "var(--area-accent)" }
);
const chipStyle = computed(() =>
	colours.value
		? { backgroundColor: colours.value.bg, color: colours.value.ink }
		: { backgroundColor: "var(--area-soft)", color: "var(--area-accent)" }
);
</script>
