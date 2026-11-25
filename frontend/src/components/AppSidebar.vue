<template>
	<div class="flex h-full flex-col bg-surface">
		<div class="flex min-h-topbar items-center border-b border-line px-4">
			<CompanyBrand />
		</div>
		<nav
			ref="nav"
			class="relative flex-1 overflow-y-auto px-3 py-4"
			aria-label="Main"
			data-testid="sellos-nav"
		>
			<!-- The solid brand highlight slides to the open page. -->
			<span
				v-show="highlight.visible"
				class="ui-nav-highlight"
				:style="{
					transform: `translateY(${highlight.top}px)`,
					height: `${highlight.height}px`,
				}"
				aria-hidden="true"
				data-testid="sellos-nav-highlight"
			/>

			<router-link
				v-for="item in top"
				:key="item.key"
				:to="item.to"
				:data-testid="`sellos-nav-${item.key}`"
				exact-active-class="ui-nav-current"
				class="ui-nav-item mb-4"
			>
				<span
					:class="ICONS[item.key] || 'lucide-circle'"
					class="icon-inherit mr-3 size-4 shrink-0"
					aria-hidden="true"
				/>
				{{ item.label }}
			</router-link>

			<div v-for="section in sections" :key="section.key" class="mb-2">
				<button
					type="button"
					class="ui-nav-section"
					:aria-expanded="isOpen(section) ? 'true' : 'false'"
					:aria-controls="`nav-section-${section.key}`"
					:data-testid="`sellos-nav-group-${section.key}`"
					@click="toggle(section)"
				>
					<span class="ui-area-chip" :data-area="section.key" aria-hidden="true">
						<span :class="section.icon" class="icon-inherit size-3.5" />
					</span>
					<span class="flex-1">{{ section.label }}</span>
					<span
						:class="isOpen(section) ? 'lucide-chevron-down' : 'lucide-chevron-right'"
						class="icon-inherit size-4 shrink-0"
						aria-hidden="true"
					/>
				</button>
				<div v-show="isOpen(section)" :id="`nav-section-${section.key}`" class="mt-1">
					<router-link
						v-for="item in section.items"
						:key="item.key"
						:to="item.to"
						:data-testid="`sellos-nav-${item.key}`"
						active-class="ui-nav-current"
						exact-active-class="ui-nav-current"
						class="ui-nav-item mb-0.5"
					>
						<span
							:class="ICONS[item.key] || 'lucide-circle'"
							class="icon-inherit mr-3 size-4 shrink-0"
							aria-hidden="true"
						/>
						<span class="flex-1">{{ item.label }}</span>
						<span
							v-if="countFor(item)"
							class="ui-count-badge"
							:data-testid="`sellos-nav-count-${item.key}`"
							:aria-label="`${countFor(item)} waiting`"
							>{{ countFor(item) }}</span
						>
					</router-link>
				</div>
			</div>
		</nav>
		<div class="border-t border-line p-3">
			<button
				type="button"
				class="ui-nav-item"
				data-testid="sellos-signout"
				@click="signOut()"
			>
				<span
					class="lucide-log-out icon-inherit mr-3 size-4 shrink-0"
					aria-hidden="true"
				/>
				Sign out
			</button>
		</div>
	</div>
</template>

<script setup>
// The sidebar (docs/DESIGN_SYSTEM.md, section 2): the square logo mark, Home on its own, then one section for each
// SellOS area with its area chip, a small uppercase label and a chevron. Items are 44px high with the control radius.
// The open page is a solid brand gradient highlight with white text and the button shadow, which slides between
// items. Which sections are open is kept per person on the server (sellos.access.preferences); a section holding
// the open page is always open. A person sees only the links of their own role (personas.js).
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";

import CompanyBrand from "./CompanyBrand.vue";
import { logBackgroundError } from "../api";
import { AREA_ORDER, areaOfItem, areas } from "../areas";
import { ICONS } from "../navIcons";
import { navCounts, refreshWhatsAppCount } from "../navCounts";
import { groupLabel, navFor, personaFor } from "../personas";
import { loadNavState, saveNavState } from "../navState";
import { session, signOut } from "../session";

const route = useRoute();
const nav = ref(null);

const items = computed(() => navFor(personaFor(session.roles)));
const top = computed(() => items.value.filter((item) => item.key === "home"));
const sections = computed(() =>
	AREA_ORDER.map((key) => ({
		key,
		label: groupLabel(personaFor(session.roles), key, areas[key].label),
		icon: areas[key].icon,
		items: items.value.filter((item) => item.key !== "home" && areaOfItem(item) === key),
	})).filter((section) => section.items.length)
);

const closed = reactive({});
const holdsRoute = (section) =>
	section.items.some((item) => route.path === item.to || route.path.startsWith(`${item.to}/`));
const isOpen = (section) => !closed[section.key] || holdsRoute(section);

function toggle(section) {
	// A section holding the open page stays open, so there is nothing to close or to remember for it.
	if (isOpen(section) && holdsRoute(section)) return;
	closed[section.key] = isOpen(section);
	saveNavState(Object.keys(closed).filter((key) => closed[key]));
	slide();
}

// The sliding highlight: placed over the item of the open page.
const highlight = reactive({ visible: false, top: 0, height: 44 });
async function slide() {
	await nextTick();
	const root = nav.value;
	const current = root?.querySelector(".ui-nav-current");
	if (!root || !current || current.offsetParent === null) {
		highlight.visible = false;
		return;
	}
	highlight.top = current.offsetTop;
	highlight.height = current.offsetHeight;
	highlight.visible = true;
}
watch(() => route.fullPath, slide);
watch(sections, slide);

const countFor = (item) =>
	item.key === "queue" ? navCounts.queue : item.key === "whatsapp" ? navCounts.whatsapp : 0;

const hasWhatsApp = computed(() => items.value.some((item) => item.key === "whatsapp"));
watch(
	() => route.path,
	() => hasWhatsApp.value && refreshWhatsAppCount()
);

onMounted(async () => {
	slide();
	if (hasWhatsApp.value) refreshWhatsAppCount();
	try {
		for (const key of await loadNavState()) closed[key] = true;
		slide();
	} catch (e) {
		logBackgroundError("nav state failed", e);
	}
});
</script>
