<template>
	<footer class="ui-form-footer" data-testid="sellos-form-footer">
		<span v-if="dirty" class="ui-text-muted mr-auto" role="status"
			>You have unsaved changes.</span
		>
		<slot name="start" />
		<AppButton
			type="button"
			:disabled="!dirty || busy"
			data-testid="sellos-form-undo"
			@click="emit('undo')"
		>
			Undo changes
		</AppButton>
		<AppButton
			type="submit"
			variant="primary"
			:disabled="busy"
			data-testid="sellos-form-save"
			@click="emit('save')"
		>
			{{ saveLabel }}
		</AppButton>
	</footer>
</template>

<script setup>
// The sticky footer of a form or settings screen: Save (solid) and Undo changes (outline).
import AppButton from "./AppButton.vue";

defineProps({
	dirty: { type: Boolean, default: false },
	busy: { type: Boolean, default: false },
	saveLabel: { type: String, default: "Save" },
});
const emit = defineEmits(["save", "undo"]);
</script>
