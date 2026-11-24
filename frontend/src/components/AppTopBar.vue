<template>
	<header
		class="sticky top-0 z-20 flex min-h-topbar items-center justify-between gap-ui-md border-b border-line bg-surface px-ui-md py-2 text-ink sm:px-ui-lg"
		data-testid="sellos-phone-topbar"
	>
		<div class="flex min-w-0 items-center gap-ui-sm">
			<!-- Phone and tablet: the sidebar is gone, so the brand sits here. -->
			<div class="min-w-0 lg:hidden"><CompanyBrand /></div>
			<p class="hidden min-w-0 truncate text-sm lg:block" data-testid="sellos-crumb">
				<template v-if="crumb">{{ crumb }} / </template
				><b class="font-semibold">{{ shell.title || "Home" }}</b>
			</p>
		</div>

		<div class="relative flex shrink-0 items-center gap-ui-sm">
			<SearchDialog v-if="canSearch" />
			<NotificationBell />
			<button
				type="button"
				class="flex min-h-touch items-center gap-2 rounded-badge py-1 pl-1 pr-2 transition hover:bg-brand-soft"
				:aria-expanded="menuOpen ? 'true' : 'false'"
				aria-haspopup="true"
				data-testid="sellos-user-button"
				@click="menuOpen = !menuOpen"
			>
				<span
					class="flex h-9 w-9 items-center justify-center rounded-badge bg-brand text-xs font-semibold text-on-brand"
					aria-hidden="true"
					>{{ badge }}</span
				>
				<span class="hidden max-w-[160px] truncate text-sm font-medium md:inline">{{
					session.fullName
				}}</span>
				<span
					class="lucide-chevron-down icon-inherit hidden size-4 md:block"
					aria-hidden="true"
				/>
			</button>
			<div
				v-if="menuOpen"
				class="absolute right-0 top-full z-30 mt-1 w-64 max-w-[calc(100vw-2rem)] rounded-card border border-line bg-surface p-2 text-ink shadow-lift"
				data-testid="sellos-user-menu"
			>
				<p class="truncate px-3 py-2 text-sm font-semibold">{{ session.fullName }}</p>
				<button
					type="button"
					class="flex min-h-touch w-full items-center gap-2 rounded-input px-3 text-left text-sm hover:bg-surface-muted"
					data-testid="sellos-menu-signout"
					@click="signOut()"
				>
					<span class="lucide-log-out size-4 text-ink-muted" aria-hidden="true" />
					Sign out
				</button>
			</div>
		</div>
		<!-- The phone's own sign out, as before the new shell. -->
		<button
			type="button"
			class="min-h-touch min-w-touch shrink-0 whitespace-nowrap rounded-input px-3 text-base lg:hidden"
			data-testid="sellos-phone-signout"
			@click="signOut()"
		>
			Sign out
		</button>
	</header>
</template>

<script setup>
// PAMAA's AppTopBar (SOS-UI-2B), adapted: white with a bottom line. Breadcrumb, search, the
// notification bell (SellOS's own), and the user button with its menu. PAMAA's help panel, offline
// badge, waiting-to-send link and role switch are left out (see docs/UI_STYLE.md, copy list).
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import CompanyBrand from "./CompanyBrand.vue";
import NotificationBell from "./NotificationBell.vue";
import SearchDialog from "./SearchDialog.vue";
import { personaFor } from "../personas";
import { session, signOut } from "../session";
import { shell } from "../shell";

const route = useRoute();
const menuOpen = ref(false);

const crumb = computed(() => route.meta.crumb || "");
const canSearch = computed(() => ["crm", "partner"].includes(route.meta.area));
const badge = computed(() => {
	const words = String(session.fullName || session.user || "?")
		.trim()
		.split(/\s+/);
	return (
		(words[0]?.[0] || "") + (words.length > 1 ? words[words.length - 1][0] : "")
	).toUpperCase();
});

watch(
	() => route.fullPath,
	() => (menuOpen.value = false)
);
// Kept for tests that read the persona.
defineExpose({ persona: computed(() => personaFor(session.roles)) });
</script>
