<template>
	<div
		class="flex min-w-0 items-center gap-2 text-base font-semibold text-ink"
		data-testid="sellos-brand"
	>
		<img
			v-if="session.company.logo"
			:src="session.company.logo"
			:alt="session.company.name"
			class="h-8 w-auto shrink-0"
			data-testid="sellos-brand-logo"
		/>
		<span
			v-else
			class="flex h-8 w-8 shrink-0 items-center justify-center rounded-round bg-brand text-sm font-bold text-on-brand"
			aria-hidden="true"
			>{{ initial }}</span
		>
		<span class="truncate" data-testid="sellos-brand-name">{{
			session.company.name || "SellOS"
		}}</span>
	</div>
</template>

<script setup>
import { computed } from "vue";

import { session } from "../session";

const initial = computed(() => (session.company.name || "SellOS").trim().charAt(0).toUpperCase());
</script>
