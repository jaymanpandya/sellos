<template>
	<div
		class="flex min-h-screen flex-col bg-surface-muted sm:flex-row"
		data-testid="sellos-app-shell"
	>
		<header
			class="flex items-center justify-between border-b border-line bg-surface px-4 py-3 sm:hidden"
			data-testid="sellos-phone-topbar"
		>
			<CompanyBrand />
			<button
				type="button"
				class="rounded-input px-3 py-1 text-sm text-ink-muted hover:bg-brand-light"
				data-testid="sellos-phone-signout"
				@click="signOut()"
			>
				Sign out
			</button>
		</header>
		<aside class="hidden w-56 shrink-0 flex-col border-r border-line bg-surface p-4 sm:flex">
			<div class="mb-6"><CompanyBrand /></div>
			<nav class="flex-1 space-y-1" aria-label="Main" data-testid="sellos-nav">
				<router-link
					v-for="item in nav"
					:key="item.key"
					:to="item.to"
					:data-testid="`sellos-nav-${item.key}`"
					class="block rounded-input px-3 py-2 text-sm text-ink hover:bg-brand-light"
				>
					{{ item.label }}
				</router-link>
			</nav>
			<button
				type="button"
				class="rounded-input px-3 py-2 text-left text-sm text-ink-muted hover:bg-brand-light"
				data-testid="sellos-signout"
				@click="signOut()"
			>
				Sign out
			</button>
		</aside>
		<main class="min-w-0 flex-1 p-4 pb-20 sm:p-8" data-testid="sellos-page-body">
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
				class="flex-1 px-2 py-3 text-center text-sm text-ink"
			>
				{{ item.label }}
			</router-link>
		</nav>
	</div>
</template>

<script setup>
import { computed } from "vue";

import CompanyBrand from "./CompanyBrand.vue";
import { session, signOut } from "../session";
import { navFor, personaFor } from "../personas";

const nav = computed(() => navFor(personaFor(session.roles)));
</script>
