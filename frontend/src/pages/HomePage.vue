<template>
	<div class="max-w-4xl" data-testid="sellos-home">
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
		<!-- SOS-P1-26: an Agent and a Sales Manager land on Today. -->
		<TodayPage v-if="showToday" class="mt-4" />
		<p v-else class="mt-2 text-ink-muted">
			This is the SellOS app shell. Each role sees its own screens as they are built.
		</p>
	</div>
</template>

<script setup>
import { computed } from "vue";

import { session } from "../session";
import TodayPage from "./TodayPage.vue";

const showSetup = computed(
	() => !session.setupComplete && session.roles.includes("SellOS Company Admin")
);
const showToday = computed(
	() => session.roles.includes("SellOS Agent") || session.roles.includes("SellOS Sales Manager")
);
</script>
