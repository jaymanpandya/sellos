<template>
	<Button
		v-bind="$attrs"
		:variant="variant === 'primary' || variant === 'danger' ? 'solid' : 'subtle'"
		:theme="variant === 'danger' ? 'red' : 'gray'"
		size="lg"
		:class="[
			'!min-h-touch !min-w-touch !rounded-input !px-[18px] !text-base !font-medium',
			variant === 'secondary' && !active
				? '!border !border-ghost-border !bg-ghost-bg !text-ink'
				: '',
			variant === 'secondary' && active
				? '!border !border-ghost-border !bg-brand !text-on-brand-accent'
				: '',
		]"
	>
		<template v-if="$slots.prefix" #prefix><slot name="prefix" /></template>
		<slot />
	</Button>
</template>

<script setup>
// PAMAA's .pamaa-button and .pamaa-button-solid on a frappe-ui Button (SOS-UI-2B).
// primary: button/bg with text/button, one per screen. secondary: button/ghostBg and ghostBorder.
// danger: the red solid button. Every other attribute (data-testid, type, @click) goes to the button.
import { Button } from "frappe-ui";

defineOptions({ inheritAttrs: false });
defineProps({
	variant: { type: String, default: "secondary" }, // primary | secondary | danger
	active: { type: Boolean, default: false }, // a pressed toggle (List / Board)
});
</script>
