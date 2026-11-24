<template>
	<div class="flex min-w-0 items-center gap-3 text-ink" data-testid="sellos-brand">
		<img
			v-if="session.company.logo"
			:src="session.company.logo"
			:alt="session.company.name"
			class="h-9 w-auto shrink-0"
			data-testid="sellos-brand-logo"
		/>
		<!-- The logo mark: a 36px rounded square in the brand gradient with a white letter. -->
		<span
			v-else
			class="ui-logo-mark flex h-9 w-9 shrink-0 items-center justify-center rounded-control text-base font-bold"
			aria-hidden="true"
			>{{ initial }}</span
		>
		<span
			class="truncate text-xs font-semibold uppercase tracking-[0.12em]"
			data-testid="sellos-brand-name"
			>{{ session.company.name || "SellOS" }}</span
		>
	</div>
</template>

<script setup>
import { computed } from "vue";

import { session } from "../session";

const initial = computed(() => (session.company.name || "SellOS").trim().charAt(0).toUpperCase());
</script>
