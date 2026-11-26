<template>
	<img
		:src="src"
		:alt="alt"
		class="h-16 max-w-[12rem] rounded-control border border-line object-contain"
	/>
</template>

<script setup>
// A small framed picture, such as the company logo on the Company profile.
defineProps({
	src: { type: String, required: true },
	alt: { type: String, default: "" },
});
</script>
