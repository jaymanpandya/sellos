<template>
	<div
		class="flex min-h-screen flex-col bg-surface-muted sm:flex-row"
		data-testid="sellos-app-shell"
	>
		<header
			class="sticky top-0 z-10 flex min-h-topbar items-center justify-between border-b border-line bg-surface/85 px-4 backdrop-blur sm:hidden"
			data-testid="sellos-phone-topbar"
		>
			<CompanyBrand />
			<NotificationBell />
			<button
				type="button"
				class="min-h-touch min-w-touch rounded-input px-3 text-base text-ink-muted hover:bg-surface-muted"
				data-testid="sellos-phone-signout"
				@click="signOut()"
			>
				Sign out
			</button>
		</header>
		<aside
			class="hidden w-sidebar shrink-0 flex-col border-r border-line bg-surface/80 p-4 backdrop-blur sm:flex"
		>
			<div class="mb-2"><CompanyBrand /></div>
			<div class="mb-4"><NotificationBell /></div>
			<nav class="flex-1 space-y-1" aria-label="Main" data-testid="sellos-nav">
				<router-link
					v-for="item in nav"
					:key="item.key"
					:to="item.to"
					:data-testid="`sellos-nav-${item.key}`"
					:active-class="item.key === 'home' ? '' : 'ui-nav-active'"
					exact-active-class="ui-nav-active"
					class="flex min-h-touch items-center rounded-input px-3 text-base text-ink-body hover:bg-surface-muted"
				>
					{{ item.label }}
				</router-link>
			</nav>
			<button
				type="button"
				class="min-h-touch rounded-input px-3 text-left text-base text-ink-muted hover:bg-surface-muted"
				data-testid="sellos-signout"
				@click="signOut()"
			>
				Sign out
			</button>
		</aside>
		<main class="min-w-0 flex-1 px-4 pb-20 pt-5 sm:px-6" data-testid="sellos-page-body">
			<slot />
		</main>
		<nav
			class="fixed inset-x-0 bottom-0 flex border-t border-line bg-surface sm:hidden"
			aria-label="Main (phone)"
			data-testid="sellos-phone-nav"
		>
			<router-link
				v-for="item in nav"
				:key="item.key"
				:to="item.to"
				:data-testid="`sellos-phone-nav-${item.key}`"
				active-class="ui-nav-active-phone"
				class="flex min-h-[56px] flex-1 items-center justify-center px-2 text-center text-base text-ink-body"
			>
				{{ item.label }}
			</router-link>
		</nav>
	</div>
</template>

<script setup>
import { computed } from "vue";

import CompanyBrand from "./CompanyBrand.vue";
import NotificationBell from "./NotificationBell.vue";
import { session, signOut } from "../session";
import { navFor, personaFor } from "../personas";

const nav = computed(() => navFor(personaFor(session.roles)));
</script>

<style scoped>
.ui-nav-active {
	background-image: var(--ui-grad-brand);
	background-color: var(--sos-brand);
	color: #fff;
	font-weight: 600;
}
.ui-nav-active-phone {
	color: var(--sos-brand);
	font-weight: 600;
}
</style>
