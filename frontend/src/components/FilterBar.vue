<template>
	<form class="ui-card mb-ui-md" role="search" @submit.prevent="emit('apply')">
		<div class="grid grid-cols-1 gap-x-ui-md gap-y-ui-md sm:grid-cols-2 xl:grid-cols-4">
			<slot />
		</div>
		<div class="mt-ui-md flex flex-wrap items-center gap-ui-sm">
			<slot name="actions">
				<AppButton type="submit" variant="primary">{{ applyLabel }}</AppButton>
				<AppButton type="button" @click="emit('clear')">{{ clearLabel }}</AppButton>
			</slot>
		</div>
	</form>
</template>

<script setup>
// A row of filters in a card: a grid of labelled FormFields, then Apply and Clear. PAMAA has no filter
// bar (its screens place .pamaa-control inputs by hand), so this is new, built from PAMAA's card,
// form grid (one column on a phone, two from 640px, four from 1280px) and buttons (SOS-UI-2B).
import AppButton from "./AppButton.vue";

defineProps({
	applyLabel: { type: String, default: "Filter" },
	clearLabel: { type: String, default: "Clear filters" },
});
const emit = defineEmits(["apply", "clear"]);
</script>
