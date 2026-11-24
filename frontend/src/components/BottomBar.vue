<template>
	<nav
		class="fixed inset-x-0 bottom-0 z-30 flex border-t border-line bg-surface text-ink-body lg:hidden"
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
			class="flex min-h-[56px] min-w-touch flex-1 flex-col items-center justify-center gap-0.5 px-1 text-center text-xs font-medium"
		>
			<span
				:class="ICONS[item.key] || 'lucide-circle'"
				class="icon-inherit size-5"
				aria-hidden="true"
			/>
			{{ item.label }}
		</router-link>
		<button
			v-if="rest.length"
			type="button"
			class="flex min-h-[56px] min-w-touch flex-1 flex-col items-center justify-center gap-0.5 px-1 text-xs font-medium"
			:aria-expanded="shell.menuOpen ? 'true' : 'false'"
			data-testid="sellos-phone-more"
			@click="shell.menuOpen = !shell.menuOpen"
		>
			<span class="lucide-ellipsis icon-inherit size-5" aria-hidden="true" />
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
				class="absolute inset-x-0 bottom-0 max-h-[80vh] overflow-y-auto rounded-t bg-surface p-ui-md pb-[calc(1rem+57px)] text-ink shadow-lift"
			>
				<router-link
					v-for="item in rest"
					:key="item.key"
					:to="item.to"
					:data-testid="`sellos-phone-nav-${item.key}`"
					exact-active-class="ui-bar-active"
					class="flex min-h-touch items-center rounded px-3 text-base"
					@click="closeMenu"
				>
					<span
						:class="ICONS[item.key] || 'lucide-circle'"
						class="icon-inherit mr-3 size-4"
						aria-hidden="true"
					/>
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

import { ICONS } from "../navIcons";
import { navFor, personaFor } from "../personas";
import { session } from "../session";
import { closeMenu, shell } from "../shell";

const items = computed(() => navFor(personaFor(session.roles)));
const shown = computed(() => (items.value.length <= 5 ? items.value : items.value.slice(0, 4)));
const rest = computed(() => (items.value.length <= 5 ? [] : items.value.slice(4)));
</script>

<style scoped>
.ui-bar-active {
	color: var(--sos-brand);
	background-color: var(--ui-brand-soft);
	font-weight: 600;
}
</style>
