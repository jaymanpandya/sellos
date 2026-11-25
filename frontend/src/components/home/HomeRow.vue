<template>
	<li
		class="flex min-h-touch items-center justify-between gap-ui-sm py-2"
		:data-testid="testid || undefined"
	>
		<div class="min-w-0">
			<p class="truncate">
				<span class="ui-text-strong">{{ title }}</span>
				<span
					v-if="source"
					class="ml-ui-sm ui-text-muted"
					data-testid="sellos-row-source"
					>{{ source }}</span
				>
			</p>
			<p v-if="line" class="ui-text-muted truncate">{{ line }}</p>
		</div>
		<div class="flex shrink-0 items-center gap-ui-sm">
			<StatusBadge v-if="badge" :tone="badgeTone" :label="badge" :title="badgeTitle" />
			<router-link :to="to" class="ui-link" :aria-label="`Open ${title}`">Open</router-link>
		</div>
	</li>
</template>

<script setup>
// One row of a dashboard card (docs/DESIGN_SYSTEM.md, section 3): a title line, a muted second line, a status
// pill and an Open link. Only the Home dashboards use it.
import StatusBadge from "../StatusBadge.vue";

defineProps({
	title: { type: String, required: true },
	line: { type: String, default: "" },
	// A lead's source: its own muted field, never joined to the name.
	source: { type: String, default: "" },
	badge: { type: String, default: "" },
	badgeTone: { type: String, default: "neutral" },
	badgeTitle: { type: String, default: "" },
	to: { type: [String, Object], required: true },
	testid: { type: String, default: "" },
});
</script>
