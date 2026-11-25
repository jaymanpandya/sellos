<template>
	<div class="mb-4">
		<router-link v-if="backTo" :to="backTo" class="ui-link-button" :data-testid="backTestid">
			<span class="lucide-arrow-left icon-inherit size-4" aria-hidden="true" />
			{{ backLabel }}
		</router-link>
		<header class="ui-record-header" data-testid="sellos-record-header">
			<div class="min-w-0">
				<div class="flex flex-wrap items-center gap-2">
					<h1 class="ui-page-title break-words" :data-testid="titleTestid">
						{{ title }}
					</h1>
					<slot name="status" />
				</div>
				<p v-if="line" class="ui-text-muted mt-0.5">{{ line }}</p>
				<slot name="line" />
			</div>
			<div v-if="$slots.actions" class="flex flex-wrap items-center gap-2">
				<slot name="actions" />
			</div>
		</header>
	</div>
</template>

<script setup>
// The record header (docs/DESIGN_SYSTEM.md): a Back link above, then a sticky bar under the top bar with the title,
// the status pill (slot `status`), one muted line (code, place, owner) and the actions on the right (Edit is the
// solid button). It draws the page's one h1.
defineProps({
	title: { type: String, required: true },
	line: { type: String, default: "" },
	backTo: { type: [String, Object], default: null },
	backLabel: { type: String, default: "Back" },
	titleTestid: { type: String, default: "sellos-record-title" },
	backTestid: { type: String, default: "sellos-record-back" },
});
</script>
