<template>
	<KpiStrip :items="items" />
</template>

<script setup>
// The counts of an import, as a KPI strip of four cards (SOS-P4-10C).
import { computed } from "vue";

import KpiStrip from "../components/KpiStrip.vue";

const props = defineProps({ counts: { type: Object, required: true } });
const items = computed(() => [
	{ label: "Rows", value: props.counts.rows, caption: "in the file", icon: "lucide-rows-3" },
	{
		label: "Created",
		value: props.counts.created,
		caption: "new records",
		icon: "lucide-plus",
		tone: "success",
	},
	{
		label: "Updated",
		value: props.counts.updated,
		caption: `${props.counts.unchanged} unchanged`,
		icon: "lucide-pencil",
		tone: "info",
	},
	{
		label: "Failed",
		value: props.counts.failed,
		caption: "left out",
		icon: "lucide-circle-slash",
		tone: "warning",
	},
]);
</script>
