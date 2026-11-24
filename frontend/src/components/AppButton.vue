<template>
	<button
		v-bind="$attrs"
		:type="$attrs.type || 'button'"
		:class="classes"
		:aria-label="variant === 'icon' ? label || $attrs['aria-label'] : $attrs['aria-label']"
		:title="variant === 'icon' ? label : $attrs.title"
	>
		<slot name="prefix" />
		<slot />
	</button>
</template>

<script setup>
// The one button (docs/DESIGN_SYSTEM.md, section 4). 44px high, 18px side padding, 16px text, 10px radius.
//   primary    solid: brand gradient, white text, button shadow. The main action of a screen or card.
//   secondary  outline (the default): white, brand border at 35 percent, brand text, soft brand fill on hover.
//   link       brand text, underlined with a soft line, 44px tap area. Back links, View all.
//   danger     outline in red; add `confirm` for the solid red of the final confirming button.
//   icon       a square 44px outline button with a tooltip (label) and an accessible name.
// Every other attribute (data-testid, type, @click, disabled) goes to the button.
import { computed } from "vue";

defineOptions({ inheritAttrs: false });
const props = defineProps({
	variant: { type: String, default: "secondary" }, // primary | secondary | link | danger | icon
	active: { type: Boolean, default: false }, // a pressed toggle (List / Board)
	confirm: { type: Boolean, default: false }, // danger only: the solid red confirming button
	label: { type: String, default: "" }, // icon only: tooltip and accessible name
});

const classes = computed(() => {
	if (props.variant === "link") return ["ui-link-button"];
	const list = ["ui-button"];
	if (props.variant === "primary") list.push("ui-button-solid");
	if (props.variant === "danger")
		list.push(props.confirm ? "ui-button-danger-solid" : "ui-button-danger");
	if (props.variant === "icon") list.push("ui-button-icon");
	if (props.active) list.push("ui-button-active");
	return list;
});
</script>
