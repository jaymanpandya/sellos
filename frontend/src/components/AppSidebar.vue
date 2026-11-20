<template>
	<div class="flex h-full flex-col bg-brand">
		<div class="flex min-h-topbar items-center border-b border-white/15 px-ui-md">
			<CompanyBrand />
		</div>
		<nav
			class="flex-1 overflow-y-auto px-ui-md py-ui-md"
			aria-label="Main"
			data-testid="sellos-nav"
		>
			<div v-for="section in sections" :key="section.key" class="mb-ui-lg">
				<p
					v-if="section.label"
					class="mb-1 px-3 py-1 text-heading uppercase text-on-brand opacity-80"
				>
					{{ section.label }}
				</p>
				<router-link
					v-for="item in section.items"
					:key="item.key"
					:to="item.to"
					:data-testid="`sellos-nav-${item.key}`"
					:active-class="item.key === 'home' ? '' : 'ui-nav-active'"
					exact-active-class="ui-nav-active"
					class="ui-nav-item flex min-h-touch items-center rounded-input px-3 text-base text-on-brand transition-colors duration-150 hover:bg-white/10"
				>
					<span
						:class="ICONS[item.key] || 'lucide-circle'"
						class="icon-inherit mr-3 size-4 shrink-0"
						aria-hidden="true"
					/>
					{{ item.label }}
				</router-link>
			</div>
		</nav>
		<div class="border-t border-white/15 p-ui-md">
			<button
				type="button"
				class="flex min-h-touch w-full items-center rounded-input px-3 text-left text-base text-on-brand hover:bg-white/10"
				data-testid="sellos-signout"
				@click="signOut()"
			>
				Sign out
			</button>
		</div>
	</div>
</template>

<script setup>
// PAMAA's AppSidebar (SOS-UI-2B), adapted: the menu is the persona's navigation (personas.js), grouped
// by area into labelled sections. The sections stay open (the longest menu has 11 places) and the
// highlight does not slide. Current item: surface/accent with text/accent. The links are the same
// anchors, in the same order, with the same data-testid as before.
import { computed } from "vue";

import CompanyBrand from "./CompanyBrand.vue";
import { ICONS } from "../navIcons";
import { navFor, personaFor } from "../personas";
import { session, signOut } from "../session";

const SECTION_LABELS = {
	home: "",
	crm: "Sales",
	company: "Company",
	reports: "Reports",
	platform: "Platform",
	partner: "Partner",
	client: "",
};

const sections = computed(() => {
	const out = [];
	for (const item of navFor(personaFor(session.roles))) {
		let section = out[out.length - 1];
		if (!section || section.key !== item.area) {
			section = { key: item.area, label: SECTION_LABELS[item.area] ?? "", items: [] };
			out.push(section);
		}
		section.items.push(item);
	}
	return out;
});
</script>

<style scoped>
.ui-nav-active {
	background-color: var(--sos-brand-mid);
	color: var(--sos-on-brand-accent);
	font-weight: 600;
}
</style>
