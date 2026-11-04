<template>
	<div class="flex items-center gap-2 text-lg font-semibold text-brand">
		<img
			v-if="session.company.logo"
			:src="session.company.logo"
			:alt="session.company.name"
			class="h-8 w-auto"
		/>
		<span>{{ session.company.name || "SellOS" }}</span>
	</div>
</template>

<script setup>
import { session } from "../session";
</script>
