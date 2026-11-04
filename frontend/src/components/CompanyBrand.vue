<template>
	<div
		class="flex items-center gap-2 text-lg font-semibold text-brand"
		data-testid="sellos-brand"
	>
		<img
			v-if="session.company.logo"
			:src="session.company.logo"
			:alt="session.company.name"
			class="h-8 w-auto"
			data-testid="sellos-brand-logo"
		/>
		<span data-testid="sellos-brand-name">{{ session.company.name || "SellOS" }}</span>
	</div>
</template>

<script setup>
import { session } from "../session";
</script>
