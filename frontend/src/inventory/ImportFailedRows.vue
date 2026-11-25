<template>
	<ul v-if="failed.length" class="mt-ui-md ui-text-muted" :data-testid="testId">
		<li v-for="f in failed" :key="f.row">Row {{ f.row }}: {{ f.reason }}</li>
	</ul>
</template>

<script setup>
// The rows an import could not save, each with its reason (SOS-P4-10C).
defineProps({
	failed: { type: Array, required: true },
	testId: { type: String, required: true },
});
</script>
