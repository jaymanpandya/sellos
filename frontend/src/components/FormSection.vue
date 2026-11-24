<template>
	<section :aria-labelledby="headingId">
		<h3 :id="headingId" class="ui-card-heading mb-ui-md border-b border-line-soft pb-ui-sm">
			{{ title }}
		</h3>
		<div class="grid grid-cols-1 gap-x-ui-md gap-y-ui-md md:grid-cols-2">
			<slot />
		</div>
	</section>
</template>

<script setup>
// A headed group of fields: two columns from 768px, one on a phone. A field that needs the full width
// takes class="md:col-span-2".
import { useId } from "vue";

defineProps({ title: { type: String, required: true } });
const headingId = useId();
</script>
