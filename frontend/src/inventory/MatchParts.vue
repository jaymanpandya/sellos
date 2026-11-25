<template>
	<ul class="mt-ui-sm space-y-1 ui-text-muted" data-testid="sellos-match-parts">
		<li
			v-for="p in parts"
			:key="p.key"
			data-testid="sellos-match-part"
			:data-part="p.key"
			:data-applies="p.applies"
		>
			<span class="ui-text-body">{{ p.label }}</span>
			<template v-if="p.applies"
				>: {{ p.score }} out of 100, {{ p.points }} points.</template
			>
			<template v-else>: left out.</template>
			<span data-testid="sellos-match-reason"> {{ p.reason }}.</span>
		</li>
	</ul>
</template>

<script setup>
// The four parts of a match score with the reason for each (SOS-P7-08).
defineProps({ parts: { type: Array, required: true } });
</script>
