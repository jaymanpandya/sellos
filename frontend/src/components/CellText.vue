<template>
	<span
		v-if="shown"
		class="block min-w-0 max-w-full"
		:class="[
			lines === 1 ? 'truncate' : 'line-clamp-2 break-words',
			muted ? 'ui-text-muted' : '',
		]"
		:title="shown"
		data-testid="sellos-cell-text"
	>
		<slot>{{ shown }}</slot>
	</span>
	<span v-else-if="!blank" class="block ui-text-muted" data-testid="sellos-cell-empty"
		>Not set</span
	>
</template>

<script setup>
// One value of a table cell (docs/DESIGN_SYSTEM.md, "Lists"): plain text, cut with an ellipsis after one line
// (or two with `lines`), with the full text in the tooltip. An empty value reads a muted "Not set", or nothing
// when `blank` is given. Never a bare dash.
import { computed } from "vue";

const props = defineProps({
	value: { type: [String, Number], default: "" },
	lines: { type: Number, default: 1 },
	muted: { type: Boolean, default: false },
	// Show nothing at all for an empty value, instead of "Not set".
	blank: { type: Boolean, default: false },
	// The full text for the tooltip when the slot shows something other than `value`.
	full: { type: String, default: "" },
});
const shown = computed(
	() => props.full || (props.value === 0 ? "0" : String(props.value || "").trim())
);
</script>
