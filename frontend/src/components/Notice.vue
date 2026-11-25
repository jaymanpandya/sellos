<template>
	<div
		class="ui-notice"
		:data-tone="tone"
		:role="tone === 'info' ? 'note' : 'alert'"
		:data-testid="testid"
	>
		<p v-if="title" class="ui-text-strong">{{ title }}</p>
		<div class="ui-text-secondary mt-1"><slot /></div>
	</div>
</template>

<script setup>
// A notice: a white card with a 4px coloured left edge (amber for warnings, brand for rules and information), a
// bold one line title and a short list. Several notes are one notice, never separate boxes.
defineProps({
	tone: { type: String, default: "info" }, // info | warning | danger
	title: { type: String, default: "" },
	testid: { type: String, default: "sellos-notice" },
});
</script>
