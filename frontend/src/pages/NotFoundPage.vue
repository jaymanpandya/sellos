<template>
	<PageTemplate shape="form">
		<template #header>
			<PageHeader title="Page not found" icon="lucide-search-x" />
		</template>
		<SectionCard data-testid="sellos-not-found" title="Not found">
			<p class="ui-text-strong">This page does not exist.</p>
			<p class="ui-text-secondary mt-1">
				The address may be wrong, or the page may have moved.
			</p>
			<p class="mt-3">
				<router-link to="/" class="ui-link" data-testid="sellos-not-found-home"
					>Back to Home</router-link
				>
			</p>
		</SectionCard>
	</PageTemplate>
</template>

<script setup>
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import SectionCard from "../components/SectionCard.vue";
</script>
