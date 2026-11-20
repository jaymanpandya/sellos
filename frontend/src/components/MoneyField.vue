<template>
	<FormField
		v-bind="$attrs"
		:model-value="shown"
		:label="label"
		type="text"
		inputmode="numeric"
		autocomplete="off"
		@update:model-value="onText"
		@input="keepCaret"
	/>
</template>

<script setup>
// A rupee amount: shown with Indian grouping while it is typed (75,00,000), kept as a plain number in
// the model, so what is submitted is 7500000 (SOS-UI-2B). An empty box is an empty string. The caret
// stays on the same digit when the commas move.
import { computed } from "vue";

import FormField from "./FormField.vue";

defineOptions({ inheritAttrs: false });
const props = defineProps({
	modelValue: { type: [Number, String], default: "" },
	label: { type: String, required: true },
});
const emit = defineEmits(["update:modelValue"]);

const group = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const shown = computed(() =>
	props.modelValue === "" || props.modelValue == null
		? ""
		: group.format(Number(props.modelValue))
);

function onText(text) {
	const digits = String(text ?? "").replace(/\D/g, "");
	emit("update:modelValue", digits === "" ? "" : Number(digits));
}

// After the model re-renders the grouped text, put the caret back after the same number of digits.
function keepCaret(event) {
	const input = event.target;
	if (!input || input.selectionStart == null) return;
	const before = input.value.slice(0, input.selectionStart).replace(/\D/g, "").length;
	requestAnimationFrame(() => {
		let seen = 0;
		let at = input.value.length;
		for (let i = 0; i < input.value.length; i++) {
			if (seen === before) {
				at = i;
				break;
			}
			if (/\d/.test(input.value[i])) seen++;
		}
		if (seen === before && at === input.value.length) at = input.value.length;
		input.setSelectionRange(at, at);
	});
}
</script>
