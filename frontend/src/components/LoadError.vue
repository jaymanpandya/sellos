<template>
	<div
		class="flex items-start gap-ui-md rounded border border-tone-warning-line bg-tone-warning-bg p-ui-md text-sm text-tone-warning"
		role="alert"
	>
		<span
			class="lucide-triangle-alert icon-inherit mt-0.5 size-5 shrink-0"
			aria-hidden="true"
		/>
		<div>
			<p>{{ message }}</p>
			<button
				v-if="retry"
				type="button"
				class="ui-link mt-1 inline-flex min-h-touch items-center text-sm font-medium"
				@click="emit('retry')"
			>
				Try again
			</button>
		</div>
	</div>
</template>

<script setup>
// PAMAA's LoadError (SOS-UI-2B): what went wrong in plain words and a Try again link.
defineProps({
	message: { type: String, required: true },
	retry: { type: Boolean, default: true },
});
const emit = defineEmits(["retry"]);
</script>
