<template>
	<section class="ui-card" :aria-labelledby="headingId">
		<h2 v-if="title" :id="headingId" class="ui-card-heading mb-ui-md">{{ title }}</h2>
		<slot />
	</section>
</template>

<script setup>
// The card that holds a list or a table: white, 16px radius, the teal/900 line at 20%, an uppercase
// heading. PAMAA has no component of this name; its pages repeat .pamaa-card + .pamaa-heading, so
// SellOS names the pair once (SOS-UI-2B).
import { useId } from "vue";

defineProps({ title: { type: String, default: "" } });
const headingId = useId();
</script>
