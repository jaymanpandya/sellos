<template>
	<div class="max-w-4xl" data-testid="sellos-home">
		<PageHeader
			:title="`Welcome${session.fullName ? ', ' + session.fullName : ''}`"
			title-testid="sellos-home-welcome"
			text="Your day at a glance."
			icon="lucide-house"
		/>
		<router-link
			v-if="showSetup"
			to="/company/setup"
			class="ui-card mb-ui-md block text-ink"
			data-testid="sellos-home-setup-banner"
		>
			Finish setting up your company. It takes a few minutes.
		</router-link>
		<!-- SOS-P1-26: an Agent and a Sales Manager land on Today. -->
		<TodayPage v-if="showToday" />
		<EmptyState
			v-else
			title="This is the SellOS app shell."
			text="Each role sees its own screens as they are built."
			icon="lucide-layout-dashboard"
		/>
	</div>
</template>

<script setup>
import { computed } from "vue";

import EmptyState from "../components/EmptyState.vue";
import PageHeader from "../components/PageHeader.vue";
import { session } from "../session";
import TodayPage from "./TodayPage.vue";

const showSetup = computed(
	() => !session.setupComplete && session.roles.includes("SellOS Company Admin")
);
const showToday = computed(
	() => session.roles.includes("SellOS Agent") || session.roles.includes("SellOS Sales Manager")
);
</script>
