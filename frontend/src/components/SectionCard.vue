<template>
	<section class="ui-card" :aria-labelledby="headingId">
		<header v-if="title || $slots.actions" class="mb-4 flex items-start justify-between gap-3">
			<div class="min-w-0">
				<div class="flex flex-wrap items-center gap-2">
					<h2 :id="headingId" class="ui-card-heading">{{ title }}</h2>
					<span v-if="tag" class="ui-tag">{{ tag }}</span>
				</div>
				<p v-if="help" class="ui-text-muted mt-1">{{ help }}</p>
			</div>
			<div v-if="$slots.actions" class="flex shrink-0 flex-wrap items-center gap-2">
				<slot name="actions" />
			</div>
		</header>
		<slot />
		<footer
			v-if="$slots.footer"
			class="mt-4 flex flex-wrap items-center justify-end gap-2 border-t border-line-soft pt-4"
		>
			<slot name="footer" />
		</footer>
	</section>
</template>

<script setup>
// The section card (docs/DESIGN_SYSTEM.md): a white card with the small uppercase heading and an optional tag chip,
// an optional line of help, the content (usually a FieldGrid) and an optional footer row for the card's actions.
// The heading is the only heading a page draws: a page never writes an h2.
import { useId } from "vue";

defineProps({
	title: { type: String, default: "" },
	tag: { type: String, default: "" },
	help: { type: String, default: "" },
});
const headingId = useId();
</script>
