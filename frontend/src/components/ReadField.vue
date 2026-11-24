<template>
	<div class="min-w-0">
		<dt class="ui-text-muted">{{ label }}</dt>
		<dd class="mt-0.5 break-words">
			<slot>
				<span v-if="filled" class="ui-text-body">{{ value }}</span>
				<span v-else class="ui-text-muted">Not filled in</span>
			</slot>
		</dd>
	</div>
</template>

<script setup>
// A read only field: a small muted label above the value in ink. A missing value reads "Not filled in" in muted
// text, never a blank or a dash. Put several in a `<dl>` inside a FieldGrid.
import { computed } from "vue";

const props = defineProps({
	label: { type: String, required: true },
	value: { type: [String, Number], default: "" },
});
const filled = computed(
	() => props.value !== "" && props.value !== null && props.value !== undefined
);
</script>
