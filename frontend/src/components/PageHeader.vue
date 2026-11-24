<template>
	<header class="ui-page-header" data-testid="sellos-page-header">
		<div class="flex min-w-0 items-center gap-4">
			<span v-if="areaIcon" class="ui-icon-chip" aria-hidden="true">
				<span :class="areaIcon" class="icon-inherit size-5" />
			</span>
			<div class="min-w-0">
				<h1 class="ui-page-title" :data-testid="titleTestid">{{ title }}</h1>
				<p v-if="text" class="ui-page-lead">{{ text }}</p>
			</div>
		</div>
		<!-- Any number of outline buttons, then at most one solid button, the main action, on the right. -->
		<div v-if="$slots.default" class="flex flex-wrap items-center gap-2">
			<slot />
		</div>
	</header>
</template>

<script setup>
// The page header (docs/DESIGN_SYSTEM.md): a 44px round area icon chip, the title (24px, semibold), one line of plain
// explanation (muted, no wider than 48rem), and on the right the actions. The chip takes the area's colours; `icon`
// overrides the area's icon. It draws the page's one h1.
import { computed } from "vue";
import { useRoute } from "vue-router";

import { areas } from "../areas";
import { navFor, personaFor } from "../personas";
import { areaKeyFor } from "../areas";
import { session } from "../session";

const props = defineProps({
	title: { type: String, required: true },
	text: { type: String, default: "" },
	icon: { type: String, default: "" },
	titleTestid: { type: String, default: "sellos-page-title" },
});
const route = useRoute();
const areaIcon = computed(
	() =>
		props.icon ||
		areas[areaKeyFor(route.path, route, navFor(personaFor(session.roles)))]?.icon ||
		""
);
</script>
