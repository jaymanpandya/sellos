<template>
	<!-- Shimmer rows in the shape of the list while its data comes in: never a bare word. -->
	<div role="status" aria-live="polite">
		<span class="sr-only">{{ label }}</span>
		<div aria-hidden="true">
			<div
				v-for="index in rows"
				:key="index"
				class="flex items-center gap-ui-md border-b border-line-soft py-ui-md last:border-b-0"
			>
				<div class="ui-shimmer h-4 flex-[2] rounded" />
				<div class="ui-shimmer hidden h-4 flex-1 rounded sm:block" />
				<div class="ui-shimmer h-5 w-16 rounded-badge" />
			</div>
		</div>
	</div>
</template>

<script setup>
// PAMAA's LoadingSkeleton, rows only (SOS-UI-2B).
defineProps({
	rows: { type: Number, default: 5 },
	label: { type: String, default: "Getting the latest details" },
});
</script>
