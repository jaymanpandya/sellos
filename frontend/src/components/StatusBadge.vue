<template>
	<Badge
		:theme="BADGE_THEME[tone] || 'gray'"
		variant="subtle"
		size="lg"
		:class="['!rounded-round', tone === 'danger' ? 'ui-pill-flash' : '']"
		v-bind="$attrs"
	>
		<template #prefix>
			<span
				:class="toneIcon(tone)"
				class="icon-inherit size-3.5 shrink-0"
				aria-hidden="true"
			/>
		</template>
		<slot>{{ label }}</slot>
	</Badge>
</template>

<script setup>
// PAMAA's StatusPill on a frappe-ui Badge: the word and an icon, never colour alone (SOS-UI-2B).
import { Badge } from "frappe-ui";

import { BADGE_THEME, toneIcon } from "../toneIcons";

defineOptions({ inheritAttrs: false });
defineProps({
	label: { type: String, default: "" },
	// success, warning, danger, info or neutral
	tone: { type: String, default: "neutral" },
});
</script>
