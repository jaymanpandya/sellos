<template>
	<div class="flex flex-col gap-1.5">
		<label :for="id" class="block text-sm text-ink-muted">
			{{ label }}<span v-if="required" class="text-tone-danger" aria-hidden="true"> *</span>
		</label>
		<input
			:id="id"
			type="file"
			:accept="accept"
			:required="required"
			v-bind="$attrs"
			class="min-h-touch w-full rounded-input border border-line-field bg-surface px-ui-sm py-2 text-base text-ink file:mr-ui-md file:min-h-8 file:cursor-pointer file:rounded-input file:border file:border-ghost-border file:bg-ghost-bg file:px-ui-md file:py-1 file:text-base file:font-medium file:text-ink"
			@change="emit('change', $event)"
		/>
		<p v-if="hint" class="text-sm text-ink-muted">{{ hint }}</p>
	</div>
</template>

<script setup>
// A file chooser with a visible label (SOS-UI-3B). frappe-ui has no file input in its FormControl, so the
// one native file input of the app lives here, in the shared folder, in the Pandya tokens. data-testid and
// other attributes land on the input, so tests find it with selectFile. The page reads the file in `change`.
import { useId } from "vue";

defineOptions({ inheritAttrs: false });
defineProps({
	label: { type: String, required: true },
	accept: { type: String, default: "" },
	required: { type: Boolean, default: false },
	hint: { type: String, default: "" },
});
const emit = defineEmits(["change"]);
const id = useId();
</script>
