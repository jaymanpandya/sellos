<template>
	<div class="ui-empty" data-testid="sellos-empty-state">
		<span class="ui-icon-chip mb-1" aria-hidden="true">
			<span :class="icon" class="icon-inherit size-5" />
		</span>
		<p class="ui-text-strong">{{ title }}</p>
		<p v-if="text" class="ui-text-muted mx-auto max-w-md">
			{{ text }}
		</p>
		<div v-if="$slots.default" class="mt-2 flex justify-center"><slot /></div>
	</div>
</template>

<script setup>
// PAMAA's EmptyState (SOS-UI-2B): a dashed 16px box, an icon chip, a title, one line and an optional action.
defineProps({
	title: { type: String, required: true },
	text: { type: String, default: "" },
	icon: { type: String, default: "lucide-sparkles" },
});
</script>
