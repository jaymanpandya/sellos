<template>
	<div class="max-w-2xl" data-testid="sellos-home">
		<h1 class="text-2xl font-semibold text-ink" data-testid="sellos-home-welcome">
			Welcome{{ session.fullName ? ", " + session.fullName : "" }}
		</h1>
		<router-link
			v-if="showSetup"
			to="/company/setup"
			class="mt-3 block rounded-input border border-line bg-brand-light p-3 text-ink"
			data-testid="sellos-home-setup-banner"
		>
			Finish setting up your company. It takes a few minutes.
		</router-link>
		<p class="mt-2 text-ink-muted">
			This is the SellOS app shell. Each role sees its own screens as they are built.
		</p>
	</div>
</template>

<script setup>
import { computed } from "vue";

import { session } from "../session";

const showSetup = computed(
	() => !session.setupComplete && session.roles.includes("SellOS Company Admin")
);
</script>
