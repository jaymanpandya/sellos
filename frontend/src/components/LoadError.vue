<template>
	<div class="ui-error-box flex items-start gap-4" role="alert">
		<span
			class="lucide-triangle-alert icon-inherit mt-0.5 size-5 shrink-0"
			aria-hidden="true"
		/>
		<div>
			<p>{{ message }}</p>
			<AppButton v-if="retry" variant="link" @click="emit('retry')">Try again</AppButton>
		</div>
	</div>
</template>

<script setup>
import AppButton from "./AppButton.vue";

// PAMAA's LoadError (SOS-UI-2B): what went wrong in plain words and a Try again link.
defineProps({
	message: { type: String, required: true },
	retry: { type: Boolean, default: true },
});
const emit = defineEmits(["retry"]);
</script>
