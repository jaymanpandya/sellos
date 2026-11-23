<template>
	<div class="grid grid-cols-2 gap-ui-md md:grid-cols-5">
		<StatCard label="Rows" :value="counts.rows" icon="lucide-rows-3" />
		<StatCard label="Created" :value="counts.created" icon="lucide-plus" tone="success" />
		<StatCard label="Updated" :value="counts.updated" icon="lucide-pencil" tone="info" />
		<StatCard label="Unchanged" :value="counts.unchanged" icon="lucide-equal" />
		<StatCard
			label="Failed"
			:value="counts.failed"
			icon="lucide-circle-slash"
			tone="warning"
		/>
	</div>
</template>

<script setup>
// The counts of an import, as cards (SOS-P4-10C).
import StatCard from "../components/StatCard.vue";

defineProps({ counts: { type: Object, required: true } });
</script>
