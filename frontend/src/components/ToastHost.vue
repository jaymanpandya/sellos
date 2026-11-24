<template>
	<div
		class="pointer-events-none fixed inset-x-0 bottom-[var(--ui-bar,0px)] z-50 flex flex-col items-center gap-ui-sm p-4 sm:items-end"
		aria-live="polite"
		data-testid="sellos-toasts"
	>
		<TransitionGroup name="ui-toast">
			<div
				v-for="toast in toasts"
				:key="toast.id"
				class="pointer-events-auto flex min-h-touch w-full max-w-sm items-center gap-ui-md rounded border bg-surface py-2 pl-3 pr-1 text-sm shadow-lift"
				:class="TONE_CLASSES[toast.tone] || TONE_CLASSES.success"
				role="status"
				data-testid="sellos-toast"
			>
				<span
					:class="toneIcon(toast.tone)"
					class="icon-inherit size-[18px] shrink-0"
					aria-hidden="true"
				/>
				<span class="flex-1 text-ink">{{ toast.text }}</span>
				<button
					type="button"
					class="flex min-h-touch min-w-touch items-center justify-center rounded text-ink-muted hover:bg-brand-soft"
					aria-label="Close message"
					@click="dismissToast(toast.id)"
				>
					<span class="lucide-x size-4" aria-hidden="true" />
				</button>
			</div>
		</TransitionGroup>
	</div>
</template>

<script setup>
// PAMAA's ToastHost (SOS-UI-2B): bottom centre on a phone, bottom right from 640px, a tone line and icon.
import { dismissToast, toasts } from "../shell";
import { toneIcon } from "../toneIcons";

const TONE_CLASSES = {
	success: "border-tone-success-line text-tone-success",
	warning: "border-tone-warning-line text-tone-warning",
	danger: "border-tone-danger-line text-tone-danger",
	info: "border-tone-info-line text-tone-info",
};
</script>
