<template>
	<header class="ui-card mb-ui-md flex flex-wrap items-center justify-between gap-ui-md">
		<div class="flex min-w-0 items-center gap-ui-md">
			<span
				v-if="icon"
				class="hidden h-11 w-11 shrink-0 items-center justify-center rounded bg-brand-soft text-brand sm:inline-flex"
				aria-hidden="true"
			>
				<span :class="icon" class="icon-inherit size-5" />
			</span>
			<div class="min-w-0">
				<h1 class="ui-page-title" :data-testid="titleTestid">{{ title }}</h1>
				<p v-if="text" class="ui-page-lead">{{ text }}</p>
			</div>
		</div>
		<!-- Secondary actions first, the one primary action last, on the right. -->
		<div v-if="$slots.default" class="flex flex-wrap items-center gap-ui-sm">
			<slot />
		</div>
	</header>
</template>

<script setup>
// The page header card (docs/UI_STANDARD.md): icon, title, one line of purpose, and the actions on the
// right. Put secondary actions first in the slot and the one primary AppButton last. The area chip takes
// an icon class such as lucide-users.
defineProps({
	title: { type: String, required: true },
	text: { type: String, default: "" },
	icon: { type: String, default: "" },
	titleTestid: { type: String, default: "sellos-page-title" },
});
</script>
