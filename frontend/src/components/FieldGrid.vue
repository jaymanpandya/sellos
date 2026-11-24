<template>
	<div
		class="grid grid-cols-1 gap-x-5 gap-y-4"
		:class="
			columns === 3 ? 'md:grid-cols-2 lg:grid-cols-3' : columns === 1 ? '' : 'md:grid-cols-2'
		"
	>
		<slot />
	</div>
</template>

<script setup>
// A field grid: one column on a phone, two (or three) from tablet. The gap is 20px across and 16px down. A field that
// needs the whole row takes class="md:col-span-2".
defineProps({ columns: { type: Number, default: 2 } });
</script>
