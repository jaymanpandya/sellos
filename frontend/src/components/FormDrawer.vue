<template>
	<Teleport to="body">
		<div
			v-if="open"
			class="fixed inset-0 z-50 flex justify-end ui-overlay"
			data-testid="sellos-drawer-overlay"
			@mousedown.self="emit('close')"
		>
			<form
				ref="panel"
				role="dialog"
				aria-modal="true"
				:aria-labelledby="titleId"
				class="flex h-full w-full max-w-[40rem] flex-col border-l border-line bg-surface shadow-lift"
				:data-testid="testid"
				@submit.prevent="emit('submit')"
				@keydown.esc="emit('close')"
			>
				<header
					class="flex items-start justify-between gap-ui-md border-b border-line px-ui-lg py-ui-md"
				>
					<div class="min-w-0">
						<h2 :id="titleId" class="text-title text-ink">{{ title }}</h2>
						<p v-if="text" class="mt-1 text-sm text-ink-muted">{{ text }}</p>
					</div>
					<button
						type="button"
						class="inline-flex min-h-touch min-w-touch shrink-0 items-center justify-center rounded-control text-ink-muted hover:bg-brand-soft"
						aria-label="Close"
						data-testid="sellos-drawer-close"
						@click="emit('close')"
					>
						<span class="lucide-x icon-inherit size-5" aria-hidden="true" />
					</button>
				</header>
				<div class="flex-1 space-y-ui-lg overflow-y-auto px-ui-lg py-ui-lg">
					<slot />
				</div>
				<!-- The sticky footer: the primary action and Cancel. -->
				<footer
					class="flex flex-wrap items-center justify-end gap-ui-sm border-t border-line bg-surface px-ui-lg py-ui-md"
					data-testid="sellos-drawer-footer"
				>
					<slot name="footer-start" />
					<AppButton type="button" :data-testid="cancelTestid" @click="emit('close')">
						Cancel
					</AppButton>
					<AppButton
						type="submit"
						variant="primary"
						:disabled="busy"
						:data-testid="submitTestid"
					>
						{{ submitLabel }}
					</AppButton>
				</footer>
			</form>
		</div>
	</Teleport>
</template>

<script setup>
// A right side drawer for a form (docs/UI_STANDARD.md, "Forms"): nothing is an open form under a list.
// Headed sections (FormSection) in the body, two columns on a desktop, and the primary and Cancel buttons
// in a sticky footer. The form submits with the primary button or Enter; Escape and the overlay close it.
import { nextTick, ref, useId, watch } from "vue";

import AppButton from "./AppButton.vue";

const props = defineProps({
	open: { type: Boolean, default: false },
	title: { type: String, required: true },
	text: { type: String, default: "" },
	submitLabel: { type: String, default: "Save" },
	busy: { type: Boolean, default: false },
	testid: { type: String, default: "sellos-drawer" },
	submitTestid: { type: String, default: "sellos-drawer-save" },
	cancelTestid: { type: String, default: "sellos-drawer-cancel" },
});
const emit = defineEmits(["close", "submit"]);

const titleId = useId();
const panel = ref(null);

// Focus the first field when it opens, so a keyboard user can start typing.
watch(
	() => props.open,
	async (open) => {
		if (!open) return;
		await nextTick();
		panel.value?.querySelector("input, select, textarea, [role='combobox'], button")?.focus();
	}
);
</script>
