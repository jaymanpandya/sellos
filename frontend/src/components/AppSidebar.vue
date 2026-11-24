<template>
	<div class="flex h-full flex-col bg-surface">
		<div class="flex min-h-topbar items-center border-b border-line px-ui-md">
			<CompanyBrand />
		</div>
		<nav
			class="flex-1 overflow-y-auto px-ui-md py-ui-md"
			aria-label="Main"
			data-testid="sellos-nav"
		>
			<!-- Home stands alone above the groups. -->
			<router-link
				v-for="item in top"
				:key="item.key"
				:to="item.to"
				:data-testid="`sellos-nav-${item.key}`"
				exact-active-class="ui-pill-active"
				class="ui-nav-item ui-pill-hover mb-ui-md flex min-h-touch items-center rounded-control px-3 text-base text-ink-body transition-colors duration-150"
			>
				<span
					:class="ICONS[item.key] || 'lucide-circle'"
					class="icon-inherit mr-3 size-4 shrink-0"
					aria-hidden="true"
				/>
				{{ item.label }}
			</router-link>

			<div v-for="group in groups" :key="group.key" class="mb-ui-sm">
				<button
					type="button"
					class="flex min-h-touch w-full items-center gap-2 rounded-control px-3 text-left text-heading uppercase text-ink-muted hover:bg-surface-faint"
					:aria-expanded="isOpen(group) ? 'true' : 'false'"
					:aria-controls="`nav-group-${group.key}`"
					:data-testid="`sellos-nav-group-${group.key}`"
					@click="toggle(group)"
				>
					<span
						:class="group.icon"
						class="icon-inherit size-4 shrink-0"
						aria-hidden="true"
					/>
					<span class="flex-1">{{ group.label }}</span>
					<span
						:class="isOpen(group) ? 'lucide-chevron-down' : 'lucide-chevron-right'"
						class="icon-inherit size-4 shrink-0"
						aria-hidden="true"
					/>
				</button>
				<div v-show="isOpen(group)" :id="`nav-group-${group.key}`" class="mt-0.5">
					<router-link
						v-for="item in group.items"
						:key="item.key"
						:to="item.to"
						:data-testid="`sellos-nav-${item.key}`"
						active-class="ui-pill-active"
						exact-active-class="ui-pill-active"
						class="ui-nav-item ui-pill-hover mb-0.5 flex min-h-touch items-center rounded-control px-3 text-base text-ink-body transition-colors duration-150"
					>
						<span
							:class="ICONS[item.key] || 'lucide-circle'"
							class="icon-inherit mr-3 size-4 shrink-0"
							aria-hidden="true"
						/>
						<span class="flex-1">{{ item.label }}</span>
						<span
							v-if="countFor(item)"
							class="ml-2 rounded-round bg-brand px-2 text-xs font-semibold text-on-brand"
							:data-testid="`sellos-nav-count-${item.key}`"
							:aria-label="`${countFor(item)} waiting`"
							>{{ countFor(item) }}</span
						>
					</router-link>
				</div>
			</div>
		</nav>
		<div class="border-t border-line p-ui-md">
			<button
				type="button"
				class="ui-pill-hover flex min-h-touch w-full items-center rounded-control px-3 text-left text-base text-ink-body"
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
// The sidebar (SOS-UI-2B, regrouped by the layout pass): Home on its own, then collapsible groups, each
// with an icon and a small caps label, whose open or closed state is remembered. A person sees only the
// links and groups of their own role (personas.js). The group holding the current page is always open.
// Call queue and WhatsApp carry a count badge (navCounts.js).
import { computed, onMounted, reactive, watch } from "vue";
import { useRoute } from "vue-router";

import CompanyBrand from "./CompanyBrand.vue";
import { GROUPS, ICONS, groupOf } from "../navIcons";
import { navCounts, refreshWhatsAppCount } from "../navCounts";
import { navFor, personaFor } from "../personas";
import { session, signOut } from "../session";

const route = useRoute();
const STORE = "sellos.nav.groups";

const items = computed(() => navFor(personaFor(session.roles)));
const top = computed(() => items.value.filter((item) => item.key === "home"));
const groups = computed(() =>
	GROUPS.map((group) => ({
		...group,
		items: items.value.filter((item) => item.key !== "home" && groupOf(item) === group.key),
	})).filter((group) => group.items.length)
);

// Open or closed, kept in the browser. A group is open until the person closes it.
function readStore() {
	try {
		return JSON.parse(window.localStorage.getItem(STORE) || "{}") || {};
	} catch {
		return {};
	}
}
const closed = reactive(readStore());

const holdsRoute = (group) =>
	group.items.some((item) => {
		const path = item.to === "/" ? null : item.to;
		return path && (route.path === path || route.path.startsWith(`${path}/`));
	});
const isOpen = (group) => !closed[group.key] || holdsRoute(group);

function toggle(group) {
	// A group holding the current page stays open, so there is nothing to close or to remember for it.
	if (isOpen(group) && holdsRoute(group)) return;
	closed[group.key] = isOpen(group);
	try {
		window.localStorage.setItem(STORE, JSON.stringify({ ...closed }));
	} catch {
		// private mode: the state lasts until the page is left
	}
}

const countFor = (item) =>
	item.key === "queue" ? navCounts.queue : item.key === "whatsapp" ? navCounts.whatsapp : 0;

const hasWhatsApp = computed(() => items.value.some((item) => item.key === "whatsapp"));
onMounted(() => hasWhatsApp.value && refreshWhatsAppCount());
watch(
	() => route.path,
	() => hasWhatsApp.value && refreshWhatsAppCount()
);
</script>
