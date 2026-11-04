<template>
	<div class="max-w-3xl" data-testid="sellos-leads-page">
		<div class="flex items-center justify-between gap-3">
			<h1 class="text-2xl font-semibold text-ink">Leads</h1>
			<button
				v-if="canCreate"
				type="button"
				class="btn"
				data-testid="sellos-leads-new"
				@click="creating = !creating"
			>
				{{ creating ? "Cancel" : "New lead" }}
			</button>
		</div>

		<form
			v-if="creating"
			class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4"
			data-testid="sellos-lead-form"
			@submit.prevent="create"
		>
			<input
				v-model="form.client_name"
				data-testid="sellos-lead-form-name"
				required
				placeholder="Client name"
				class="field"
			/>
			<select v-model="form.client_type" data-testid="sellos-lead-form-type" class="field">
				<option v-for="t in CLIENT_TYPES" :key="t">{{ t }}</option>
			</select>
			<input
				v-model="form.phone"
				data-testid="sellos-lead-form-phone"
				placeholder="Phone"
				class="field"
			/>
			<input
				v-if="form.client_type === 'NRI'"
				v-model="form.overseas_phone"
				placeholder="Overseas phone (optional)"
				class="field"
			/>
			<input
				v-if="form.client_type === 'NRI'"
				v-model="form.country_of_residence"
				placeholder="Country of residence (optional)"
				class="field"
			/>
			<input
				v-model="form.email"
				data-testid="sellos-lead-form-email"
				type="email"
				placeholder="Email"
				class="field"
			/>
			<input
				v-model="form.source"
				data-testid="sellos-lead-form-source"
				placeholder="Source"
				class="field"
			/>
			<p v-if="error" data-testid="sellos-lead-form-error" class="text-sm text-accent">
				{{ error }}
			</p>
			<button type="submit" class="btn" data-testid="sellos-lead-form-save">
				Save lead
			</button>
		</form>

		<input
			v-model="search"
			data-testid="sellos-leads-search"
			placeholder="Search leads"
			class="field mt-4"
			@input="load"
		/>
		<p v-if="loadError" data-testid="sellos-leads-error" role="alert" class="mt-4 text-accent">
			{{ loadError }}
		</p>
		<p v-else-if="loading" data-testid="sellos-leads-loading" class="mt-4 text-ink-muted">
			Loading leads.
		</p>
		<p v-else-if="!leads.length" data-testid="sellos-leads-empty" class="mt-4 text-ink-muted">
			No leads yet.
		</p>
		<ul class="mt-4 divide-y divide-line rounded-input border border-line bg-surface">
			<li v-for="lead in leads" :key="lead.name" data-testid="sellos-lead-row">
				<router-link
					:to="`${basePath}/${lead.name}`"
					class="flex items-center justify-between gap-3 px-4 py-3 hover:bg-brand-light"
				>
					<span>
						<span class="block font-medium text-ink">{{ lead.client_name }}</span>
						<span class="block text-sm text-ink-muted">{{
							lead.source || "No source"
						}}</span>
					</span>
					<span
						v-if="lead.overdue_tasks"
						data-testid="sellos-lead-overdue"
						class="rounded-input bg-accent px-2 py-1 text-xs text-white"
					>
						{{ lead.overdue_tasks }} overdue
					</span>
				</router-link>
			</li>
		</ul>
		<router-view />
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { CLIENT_TYPES, crmApi, serverMessage } from "../crm/crmApi";

const route = useRoute();
const router = useRouter();
const partner = computed(() => route.meta.area === "partner");
const basePath = computed(() => (partner.value ? "/partner/leads" : "/crm/leads"));
const canCreate = computed(() => !partner.value); // a channel partner logs nothing (CLAUDE.md)
const leads = ref([]);
const search = ref("");
const creating = ref(false);
const error = ref("");
const loadError = ref("");
const loading = ref(true);
const form = reactive({
	client_name: "",
	client_type: "Buyer",
	phone: "",
	overseas_phone: "",
	country_of_residence: "",
	email: "",
	source: "",
});

async function load() {
	loading.value = true;
	loadError.value = "";
	try {
		leads.value = (await crmApi.listLeads(search.value)) || [];
	} catch (e) {
		leads.value = [];
		loadError.value = serverMessage(e, "The leads could not be loaded.");
		console.error("list_leads failed", e);
	} finally {
		loading.value = false;
	}
}

async function create() {
	error.value = "";
	try {
		const { source, ...clientValues } = form;
		const client = await crmApi.saveClient(clientValues);
		const saved = await crmApi.saveLead({ client: client.name, source });
		creating.value = false;
		Object.assign(form, { client_name: "", phone: "", email: "", source: "" });
		await load();
		router.push(`${basePath.value}/${saved.lead.name}`);
	} catch (e) {
		error.value = serverMessage(e, "The lead could not be saved.");
	}
}

onMounted(load);
</script>
