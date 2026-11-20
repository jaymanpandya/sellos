<template>
	<button
		type="button"
		class="flex min-h-touch min-w-touch shrink-0 items-center justify-center rounded-badge hover:bg-white/10"
		aria-label="Search leads"
		aria-haspopup="dialog"
		data-testid="sellos-search-open"
		@click="open = true"
	>
		<span class="lucide-search icon-inherit size-5" aria-hidden="true" />
	</button>

	<Dialog v-model="open" :options="{ title: 'Search leads', size: 'md' }">
		<template #body-content>
			<form class="space-y-ui-md" @submit.prevent="go">
				<FormField
					v-model="text"
					label="Client name, phone or source"
					data-testid="sellos-search-input"
					autofocus
				/>
				<div class="flex justify-end gap-ui-sm">
					<AppButton type="button" @click="open = false">Cancel</AppButton>
					<AppButton type="submit" variant="primary" data-testid="sellos-search-go"
						>Search</AppButton
					>
				</div>
			</form>
		</template>
	</Dialog>
</template>

<script setup>
// PAMAA's GlobalSearch (SOS-UI-2B), reduced: PAMAA searches clients, orders and screens through one
// endpoint; SellOS has one searchable list, the leads, so the dialog sends the text to the Leads
// screen, which already reads it as ?q= (SOS-P1-24). A frappe-ui Dialog and FormControl.
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Dialog } from "frappe-ui";

import AppButton from "./AppButton.vue";
import FormField from "./FormField.vue";
import { shell } from "../shell";

const route = useRoute();
const router = useRouter();
const open = ref(false);
const text = ref("");
const base = computed(() => (route.meta.area === "partner" ? "/partner/leads" : "/crm/leads"));

function go() {
	const q = text.value.trim();
	open.value = false;
	text.value = "";
	if (route.path === base.value) shell.searchRequest = { q, at: Date.now() };
	else router.push({ path: base.value, query: q ? { q } : {} });
}
</script>
