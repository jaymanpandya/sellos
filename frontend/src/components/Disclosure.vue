<template>
	<details class="ui-card px-ui-md py-ui-sm" :data-testid="testid">
		<summary class="ui-card-heading cursor-pointer" :data-testid="toggleTestid">
			{{ title }}
		</summary>
		<div class="mt-ui-sm space-y-ui-sm">
			<slot />
		</div>
	</details>
</template>

<script setup>
// A collapsed section (docs/UI_STYLE.md): a rare action kept out of the way at the bottom of a page. It is
// closed until the person opens it. The content stays in the page, so a test finds it once it is open.
defineProps({
	title: { type: String, required: true },
	testid: { type: String, default: "" },
	toggleTestid: { type: String, default: "" },
});
</script>
