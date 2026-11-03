<template>
	<div class="flex min-h-screen bg-surface-muted">
		<aside class="hidden w-56 shrink-0 border-r border-line bg-surface p-4 sm:block">
			<div class="mb-6 text-lg font-semibold text-brand">
				{{ session.company.name || "SellOS" }}
			</div>
			<nav class="space-y-1">
				<router-link
					v-for="item in nav"
					:key="item.key"
					:to="item.to"
					class="block rounded-input px-3 py-2 text-sm text-ink hover:bg-brand-light"
				>
					{{ item.label }}
				</router-link>
			</nav>
		</aside>
		<main class="min-w-0 flex-1 p-4 sm:p-8">
			<slot />
		</main>
	</div>
</template>

<script setup>
import { computed } from "vue";

import { session } from "../session";
import { personaFor } from "../personas";

const nav = computed(() => personaFor(session.roles)?.nav || []);
</script>
