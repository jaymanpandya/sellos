<template>
	<AppCheckbox
		v-if="type === 'checkbox'"
		v-bind="$attrs"
		:model-value="modelValue"
		:label="label"
		@update:model-value="emit('update:modelValue', $event)"
	/>
	<FormControl
		v-else
		v-bind="{ ...$attrs, ...selectAttrs }"
		:model-value="modelValue"
		:type="type"
		:label="label"
		:required="required"
		:description="hint"
		:options="selectOptions"
		:data-option-values="optionValues"
		variant="outline"
		size="lg"
		@update:model-value="emit('update:modelValue', $event)"
	/>
</template>

<script setup>
// PAMAA's AccessField (SOS-UI-2B) on frappe-ui's FormControl: label above the field with a red *
// when required, a 44px field with the 8px radius, a hint under it. Every field has a label: a
// visually hidden one is not allowed, so the screen reader and the person see the same name.
// type: text, number, email, date, tel, textarea, select, checkbox. For a select, `options` is a list of
// strings or { label, value }. data-testid and other attributes land on the real input (or the select's
// trigger), so tests find the control itself.
import { computed } from "vue";
import { FormControl } from "frappe-ui";

import AppCheckbox from "./AppCheckbox.vue";

defineOptions({ inheritAttrs: false });
const props = defineProps({
	modelValue: { type: [String, Number, Boolean], default: "" },
	label: { type: String, required: true },
	type: { type: String, default: "text" },
	required: { type: Boolean, default: false },
	hint: { type: String, default: "" },
	options: { type: Array, default: () => [] },
});
const emit = defineEmits(["update:modelValue"]);

const selectOptions = computed(() => (props.type === "select" ? props.options : undefined));
// A select's chosen value rides on its trigger (see below); a required select says so with aria-required,
// because frappe-ui's Select only passes `required` to its hidden native twin.
const selectAttrs = computed(() =>
	props.type === "select"
		? { value: props.modelValue, ...(props.required ? { "aria-required": "true" } : {}) }
		: {}
);
// The trigger carries the chosen value as its `value` attribute, so `should("have.value")` reads it as on a
// native select. { value: label } for tests (cypress/support/commands.js), written on the select's trigger.
const optionValues = computed(() =>
	props.type === "select"
		? JSON.stringify(
				Object.fromEntries(
					props.options.map((o) => (typeof o === "string" ? [o, o] : [o.value, o.label]))
				)
		  )
		: undefined
);
</script>
