<template>
	<div class="mb-ui-lg flex flex-wrap items-start justify-between gap-ui-md">
		<div class="flex min-w-0 items-start gap-ui-md">
			<span
				v-if="icon"
				class="mt-0.5 hidden h-11 w-11 shrink-0 items-center justify-center rounded-badge bg-brand-soft text-brand sm:inline-flex"
				aria-hidden="true"
			>
				<span :class="icon" class="icon-inherit size-5" />
			</span>
			<div class="min-w-0">
				<h1 class="ui-page-title" data-testid="sellos-page-title">{{ title }}</h1>
				<p v-if="text" class="ui-page-lead">{{ text }}</p>
			</div>
		</div>
		<div v-if="$slots.default" class="flex flex-wrap items-center gap-ui-sm">
			<slot />
		</div>
	</div>
</template>

<script setup>
// PAMAA's ListHeader (SOS-UI-2B): title 24px/600, one line of text, the actions on the right. The
// area chip takes an icon class such as lucide-users; the main action is an AppButton variant="primary".
defineProps({
	title: { type: String, required: true },
	text: { type: String, default: "" },
	icon: { type: String, default: "" },
});
</script>
