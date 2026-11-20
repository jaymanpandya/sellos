<template>
	<div ref="host" class="contents">
		<Checkbox v-bind="$attrs" :model-value="modelValue" :label="label" padding />
	</div>
</template>

<script setup>
// frappe-ui's Checkbox puts every attribute on its wrapper div and on the input, so a data-testid would
// exist twice and a test could not find "the" checkbox. This wrapper keeps frappe-ui's Checkbox and
// takes the identifying attributes off the wrapper, so data-testid, value and aria-label sit on the
// real input only (SOS-UI-2B).
import { onMounted, onUpdated, ref } from "vue";
import { Checkbox } from "frappe-ui";

defineOptions({ inheritAttrs: false });
defineProps({
	modelValue: { type: [Boolean, Number, String], default: false },
	label: { type: String, default: "" },
});

const host = ref(null);
function clean() {
	const root = host.value?.firstElementChild;
	if (!root || root.tagName === "INPUT") return;
	for (const name of ["data-testid", "aria-label", "value", "name"]) root.removeAttribute(name);
}
onMounted(clean);
onUpdated(clean);
</script>
