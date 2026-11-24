<template>
	<div
		class="min-h-screen lg:pl-sidebar"
		:class="viewport.compact ? 'ui-with-bar' : ''"
		:data-layout="viewport.compact ? 'compact' : 'wide'"
		data-testid="sellos-app-shell"
	>
		<!-- Computer (from 1024px): the sidebar stays on the left. Phone and tablet: a bottom bar. -->
		<aside
			class="fixed inset-y-0 left-0 z-40 hidden w-sidebar border-r border-line bg-surface text-ink lg:block"
		>
			<AppSidebar />
		</aside>

		<AppTopBar />
		<main ref="page" class="min-w-0 px-ui-md py-5 sm:px-ui-lg" data-testid="sellos-page-body">
			<slot />
		</main>

		<BottomBar />
		<ToastHost />
	</div>
</template>

<script setup>
// PAMAA's AppShell (SOS-UI-2B). The page background is the neutral page grey; the sidebar and top bar are
// white (docs/UI_STANDARD.md). The sidebar and the bottom bar are switched by CSS (lg = 1024px) so both stay in the
// page and the tests' visible and not visible checks keep their meaning.
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import AppSidebar from "./AppSidebar.vue";
import AppTopBar from "./AppTopBar.vue";
import BottomBar from "./BottomBar.vue";
import ToastHost from "./ToastHost.vue";
import { closeMenu } from "../shell";
import { useViewport } from "../viewport";

const route = useRoute();
const page = ref(null);
const viewport = useViewport();

function onKey(event) {
	if (event.key === "Escape") closeMenu();
}

watch(
	() => route.path,
	() => closeMenu()
);
onMounted(() => window.addEventListener("keydown", onKey));
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));
</script>
