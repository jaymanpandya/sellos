<template>
	<!-- Shimmer rows in the shape of the list while its data comes in: never a bare word. -->
	<div role="status" aria-live="polite">
		<span class="sr-only">{{ label }}</span>
		<!-- variant "cards": a row of KPI tiles; "rows" (default): list rows. -->
		<div
			v-if="variant === 'cards'"
			class="grid grid-cols-2 gap-ui-md lg:grid-cols-4"
			aria-hidden="true"
		>
			<div
				v-for="index in rows"
				:key="index"
				class="rounded-card border border-line bg-surface p-ui-md shadow-card"
			>
				<div class="ui-shimmer h-3 w-20 rounded" />
				<div class="ui-shimmer my-3 h-7 w-16 rounded" />
				<div class="ui-shimmer h-3 w-28 rounded" />
			</div>
		</div>
		<div v-else aria-hidden="true">
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
// PAMAA's LoadingSkeleton (SOS-UI-2B): list rows, or KPI tiles with variant="cards".
defineProps({
	rows: { type: Number, default: 5 },
	variant: { type: String, default: "rows" }, // rows | cards
	label: { type: String, default: "Getting the latest details" },
});
</script>
