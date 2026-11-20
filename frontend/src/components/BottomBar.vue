<template>
	<nav
		class="fixed inset-x-0 bottom-0 z-30 flex border-t border-white/15 bg-brand text-on-brand lg:hidden"
		aria-label="Main (phone)"
		data-testid="sellos-phone-nav"
	>
		<router-link
			v-for="item in shown"
			:key="item.key"
			:to="item.to"
			:data-testid="`sellos-phone-nav-${item.key}`"
			:active-class="item.key === 'home' ? '' : 'ui-bar-active'"
			exact-active-class="ui-bar-active"
			class="flex min-h-[56px] min-w-touch flex-1 items-center justify-center px-1 text-center text-xs font-medium"
		>
			{{ item.label }}
		</router-link>
		<button
			v-if="rest.length"
			type="button"
			class="flex min-h-[56px] min-w-touch flex-1 items-center justify-center px-1 text-xs font-medium"
			:aria-expanded="shell.menuOpen ? 'true' : 'false'"
			data-testid="sellos-phone-more"
			@click="shell.menuOpen = !shell.menuOpen"
		>
			More
		</button>
	</nav>

	<!-- The More drawer rises from the bottom; its backdrop closes it. -->
	<Transition name="ui-sheet">
		<div
			v-if="shell.menuOpen"
			class="fixed inset-0 z-40 lg:hidden"
			data-testid="sellos-phone-drawer"
		>
			<div class="absolute inset-0 bg-black/40" @click="closeMenu" />
			<div
				class="absolute inset-x-0 bottom-0 max-h-[80vh] overflow-y-auto rounded-t-card bg-brand p-ui-md pb-[calc(1rem+57px)] text-on-brand shadow-lift"
			>
				<router-link
					v-for="item in rest"
					:key="item.key"
					:to="item.to"
					:data-testid="`sellos-phone-nav-${item.key}`"
					exact-active-class="ui-bar-active"
					class="flex min-h-touch items-center rounded-input px-3 text-base"
					@click="closeMenu"
				>
					{{ item.label }}
				</router-link>
			</div>
		</div>
	</Transition>
</template>

<script setup>
// PAMAA's BottomBar and MoreDrawer in one piece (SOS-UI-2B): at most four places and More, and
// the other places in the drawer. A menu of five or fewer places shows them all.
import { computed } from "vue";

import { navFor, personaFor } from "../personas";
import { session } from "../session";
import { closeMenu, shell } from "../shell";

const items = computed(() => navFor(personaFor(session.roles)));
const shown = computed(() => (items.value.length <= 5 ? items.value : items.value.slice(0, 4)));
const rest = computed(() => (items.value.length <= 5 ? [] : items.value.slice(4)));
</script>

<style scoped>
.ui-bar-active {
	color: var(--sos-on-brand-accent);
	background-color: var(--sos-brand-mid);
	font-weight: 600;
}
</style>
