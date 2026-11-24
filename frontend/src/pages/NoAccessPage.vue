<template>
	<PageTemplate>
		<template #header>
			<PageHeader
				title="You do not have access to this page"
				text="If you think you should, ask your company admin to check your role."
				icon="lucide-lock"
				data-testid="sellos-no-access"
			/>
		</template>
	</PageTemplate>
</template>

<script setup>
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
</script>
