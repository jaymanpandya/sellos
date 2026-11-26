<template>
	<div class="space-y-1">
		<div class="flex items-end gap-3">
			<div class="min-w-0 flex-1">
				<FormField
					:model-value="modelValue"
					:label="label"
					:hint="hint"
					v-bind="$attrs"
					@update:model-value="emit('update:modelValue', $event)"
				/>
			</div>
			<span
				class="mb-6 inline-block h-11 w-11 shrink-0 rounded-control border border-line"
				:style="{ backgroundColor: valid ? modelValue : 'transparent' }"
				aria-hidden="true"
			/>
		</div>
		<p
			v-if="valid"
			class="ui-text-small"
			:class="ok ? 'ui-text-muted' : 'ui-text-error'"
			data-testid="sellos-colour-contrast"
		>
			Contrast against white: {{ ratio }} to 1.
			{{ ok ? "Readable." : `Too pale: it needs at least ${minimum} to 1.` }}
		</p>
		<p v-else-if="modelValue" class="ui-text-small ui-text-error">
			Enter a colour such as #1F3A5F.
		</p>
	</div>
</template>

<script setup>
// A colour field: a hex text box, a swatch, and the WCAG contrast of the colour against white, checked live against a
// minimum. The server checks the same rule when the profile is saved.
import { computed } from "vue";

import FormField from "./FormField.vue";

defineOptions({ inheritAttrs: false });
const props = defineProps({
	modelValue: { type: String, default: "" },
	label: { type: String, required: true },
	hint: { type: String, default: "" },
	minimum: { type: Number, default: 4.5 },
});
const emit = defineEmits(["update:modelValue"]);

const valid = computed(() => /^#[0-9a-fA-F]{6}$/.test(props.modelValue));
const channel = (v) => {
	const c = v / 255;
	return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
};
const ratio = computed(() => {
	if (!valid.value) return 0;
	const [r, g, b] = [1, 3, 5].map((i) => parseInt(props.modelValue.slice(i, i + 2), 16));
	const lum = 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
	return Math.round((1.05 / (lum + 0.05)) * 100) / 100;
});
const ok = computed(() => ratio.value >= props.minimum);
</script>
