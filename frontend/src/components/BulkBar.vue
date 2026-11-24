<template>
	<div
		v-if="count > 0"
		class="mb-ui-md flex flex-wrap items-end gap-ui-md rounded-card border border-brand bg-brand-soft p-ui-md"
		role="region"
		aria-label="Bulk actions"
		data-testid="sellos-bulk"
	>
		<span class="pb-3 font-semibold text-ink" data-testid="sellos-bulk-count"
			>{{ count }} selected</span
		>
		<slot />
		<AppButton type="button" data-testid="sellos-bulk-clear" @click="emit('clear')">
			Clear selection
		</AppButton>
	</div>
</template>

<script setup>
// The bulk action bar: it exists only while one or more rows are selected, shows "N selected" and the
// page's actions (reassign and so on) in the default slot.
import AppButton from "./AppButton.vue";

defineProps({ count: { type: Number, default: 0 } });
const emit = defineEmits(["clear"]);
</script>
