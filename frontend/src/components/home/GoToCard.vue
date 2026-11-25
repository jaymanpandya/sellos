<template>
	<SectionCard title="Go to">
		<ul class="space-y-1">
			<li v-for="item in links" :key="item.key">
				<router-link
					:to="item.to"
					class="flex min-h-touch items-center gap-ui-sm ui-link"
					:data-testid="`${testPrefix}-${item.key}`"
				>
					<span :class="item.icon" class="icon-inherit size-4" aria-hidden="true" />
					<span>{{ item.label }}</span>
				</router-link>
			</li>
		</ul>
	</SectionCard>
</template>

<script setup>
// The Go to card of a dashboard: the screens this role uses most, only those its navigation holds.
import SectionCard from "../SectionCard.vue";

defineProps({
	links: { type: Array, required: true }, // [{ key, label, to, icon }]
	testPrefix: { type: String, default: "sellos-home-rail" },
});
</script>
