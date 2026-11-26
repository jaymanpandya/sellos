<template>
	<div class="min-w-0 max-w-full" data-testid="sellos-name-cell">
		<span
			class="block truncate"
			:title="name"
			data-testid="sellos-name-cell-name"
			:class="name ? '' : 'ui-text-muted'"
			>{{ name || "Not set" }}</span
		>
		<span
			v-if="identifier"
			class="block truncate ui-text-muted"
			:title="identifier"
			data-testid="sellos-name-cell-key"
			>{{ identifier }}</span
		>
		<span
			v-if="detail"
			class="block truncate ui-text-muted"
			:title="detail"
			data-testid="sellos-name-cell-detail"
			>{{ detail }}</span
		>
	</div>
</template>

<script setup>
// The first column of every list (docs/DESIGN_SYSTEM.md, "Lists", rule a): the name as plain text, the muted
// phone or key identifier under it, and one muted detail line. Nothing else is joined to a name: source,
// property and status never go in it. Each line is cut with an ellipsis and shows in full in a tooltip.
defineProps({
	name: { type: String, default: "" },
	// The phone number or other key identifier.
	identifier: { type: String, default: "" },
	detail: { type: String, default: "" },
});
</script>
