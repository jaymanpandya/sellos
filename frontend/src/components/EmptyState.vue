<template>
	<div class="ui-empty" data-testid="sellos-empty-state">
		<span
			class="mb-1 inline-flex h-11 w-11 items-center justify-center rounded-round bg-brand-soft text-brand"
			aria-hidden="true"
		>
			<span :class="icon" class="icon-inherit size-5" />
		</span>
		<p class="font-semibold text-ink">{{ title }}</p>
		<p v-if="text" class="mx-auto max-w-md text-sm leading-relaxed text-ink-muted">
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
