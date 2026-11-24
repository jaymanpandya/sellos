<template>
	<div
		class="mb-ui-md flex gap-1 overflow-x-auto border-b border-line"
		role="tablist"
		:aria-label="label"
		data-testid="sellos-tabs"
	>
		<button
			v-for="tab in tabs"
			:id="`tab-${tab.key}`"
			:key="tab.key"
			type="button"
			role="tab"
			:aria-selected="modelValue === tab.key ? 'true' : 'false'"
			:aria-controls="`panel-${tab.key}`"
			:data-testid="`sellos-tab-${tab.key}`"
			class="-mb-px inline-flex min-h-touch shrink-0 items-center whitespace-nowrap border-b-2 px-ui-md text-base transition-colors"
			:class="
				modelValue === tab.key
					? 'border-brand font-semibold text-brand'
					: 'border-transparent text-ink-body hover:text-ink'
			"
			@click="emit('update:modelValue', tab.key)"
		>
			{{ tab.label }}
			<span
				v-if="tab.count !== undefined && tab.count !== ''"
				class="ml-1 rounded-pill bg-surface-subtle px-2 text-xs text-ink-body"
				>{{ tab.count }}</span
			>
		</button>
	</div>
</template>

<script setup>
// Tabs of a record page. `tabs` is [{ key, label, count }]. The page shows one panel at a time with
// v-if on the key, and gives each panel id="panel-<key>" role="tabpanel".
defineProps({
	modelValue: { type: String, required: true },
	tabs: { type: Array, required: true },
	label: { type: String, default: "Sections" },
});
const emit = defineEmits(["update:modelValue"]);
</script>
