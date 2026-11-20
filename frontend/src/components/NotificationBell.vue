<template>
	<div v-if="show" ref="root" class="relative" data-testid="sellos-notifications">
		<button
			type="button"
			class="relative flex min-h-touch min-w-touch items-center justify-center rounded-badge px-2 text-sm text-on-brand hover:bg-white/10"
			aria-label="Notifications"
			:aria-expanded="open"
			data-testid="sellos-notification-bell"
			@click="toggle()"
		>
			<svg
				class="inline h-5 w-5 align-middle"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
				<path d="M13.7 21a2 2 0 0 1-3.4 0" />
			</svg>

			<span
				v-if="state.unread > 0"
				class="ml-1 rounded-badge bg-on-brand-accent px-2 py-0.5 text-xs font-semibold text-brand"
				data-testid="sellos-notification-count"
				>{{ state.unread }}</span
			>
		</button>
		<div
			v-if="open"
			class="fixed inset-x-2 top-14 z-30 max-h-[70vh] overflow-y-auto rounded-card border border-line bg-surface text-ink shadow-lift sm:absolute sm:inset-x-auto sm:right-0 sm:top-full sm:mt-2 sm:w-80"
			role="dialog"
			aria-label="Notifications"
			data-testid="sellos-notification-panel"
		>
			<div class="flex items-center justify-between border-b border-line px-3 py-2">
				<span class="text-sm font-semibold text-ink">Unread</span>
				<button
					type="button"
					class="text-sm text-brand hover:underline disabled:text-ink-muted disabled:no-underline"
					:disabled="state.unread === 0"
					data-testid="sellos-notification-mark-all"
					@click="markAllNotificationsRead()"
				>
					Mark all read
				</button>
			</div>
			<p
				v-if="state.items.length === 0"
				class="px-3 py-4 text-sm text-ink-muted"
				data-testid="sellos-notification-empty"
			>
				Nothing new. You are up to date.
			</p>
			<ul v-else class="divide-y divide-line" data-testid="sellos-notification-list">
				<li v-for="item in state.items" :key="item.name">
					<router-link
						v-if="item.lead"
						:to="leadPath(session.roles, item.lead)"
						class="block px-3 py-2 hover:bg-brand-light"
						data-testid="sellos-notification-item"
						:data-name="item.name"
						:data-lead="item.lead"
						:data-event="item.event"
						@click="openItem(item)"
					>
						<ItemText :item="item" />
					</router-link>
					<button
						v-else
						type="button"
						class="block w-full px-3 py-2 text-left hover:bg-brand-light"
						data-testid="sellos-notification-item"
						:data-name="item.name"
						:data-event="item.event"
						@click="openItem(item)"
					>
						<ItemText :item="item" />
					</button>
				</li>
			</ul>
		</div>
	</div>
</template>

<script setup>
import { computed, defineComponent, h, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { session } from "../session";
import {
	hasBell,
	leadPath,
	markAllNotificationsRead,
	markNotificationRead,
	notificationState as state,
	refreshNotifications,
	watchNotifications,
} from "../notifications/notificationsApi";

const ItemText = defineComponent({
	props: { item: { type: Object, required: true } },
	setup: (props) => () =>
		[
			h("span", { class: "block text-sm font-semibold text-ink" }, props.item.title),
			props.item.message
				? h("span", { class: "block text-sm text-ink-muted" }, props.item.message)
				: null,
		],
});

const root = ref(null);
const open = ref(false);
const route = useRoute();
const show = computed(() => hasBell(session.roles));
let stopWatching = null;

function toggle() {
	open.value = !open.value;
	if (open.value) refreshNotifications();
}

function openItem(item) {
	open.value = false;
	markNotificationRead(item.name);
}

function closeOutside(event) {
	if (open.value && root.value && !root.value.contains(event.target)) open.value = false;
}

function closeOnEscape(event) {
	if (event.key === "Escape") open.value = false;
}

watch(
	() => route.fullPath,
	() => (open.value = false)
);

onMounted(() => {
	if (show.value) stopWatching = watchNotifications();
	document.addEventListener("click", closeOutside);
	document.addEventListener("keydown", closeOnEscape);
});
onBeforeUnmount(() => {
	if (stopWatching) stopWatching();
	document.removeEventListener("click", closeOutside);
	document.removeEventListener("keydown", closeOnEscape);
});
</script>
