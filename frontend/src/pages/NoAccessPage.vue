<template>
	<PageTemplate shape="form">
		<template #header>
			<PageHeader title="You do not have access to this page" icon="lucide-lock" />
		</template>
		<SectionCard data-testid="sellos-no-access" title="Access">
			<p class="ui-text-secondary">
				If you think you should, ask your company admin to check your role.
			</p>
		</SectionCard>
	</PageTemplate>
</template>

<script setup>
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import SectionCard from "../components/SectionCard.vue";
</script>
