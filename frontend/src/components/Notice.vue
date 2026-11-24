<template>
	<aside
		class="ui-notice"
		:data-tone="tone"
		:role="tone === 'warning' ? 'alert' : 'note'"
		:data-testid="testid"
	>
		<p v-if="title" class="ui-text-strong">{{ title }}</p>
		<div class="ui-text-secondary mt-1"><slot /></div>
	</aside>
</template>

<script setup>
// A notice: a white card with a 4px coloured left edge (amber for warnings, brand for rules and information), a
// bold one line title and a short list. Several notes are one notice, never separate boxes.
defineProps({
	tone: { type: String, default: "info" }, // info | warning
	title: { type: String, default: "" },
	testid: { type: String, default: "sellos-notice" },
});
</script>
