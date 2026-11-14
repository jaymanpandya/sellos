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
			@submit.prevent="create(false)"
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
			<section
				v-if="duplicates.length"
				role="alert"
				data-testid="sellos-duplicate-warning"
				class="space-y-3 rounded-input border border-[#e8954a] bg-[#fdf1e3] p-3 text-sm text-[#7a4a10]"
			>
				<p class="font-medium">
					This person is already in SellOS. Add the enquiry to them instead of making a
					second client.
				</p>
				<div
					v-for="match in duplicates"
					:key="match.name"
					data-testid="sellos-duplicate-match"
					:data-visible="match.visible ? 'yes' : 'no'"
					class="rounded-input border border-line bg-surface p-3 text-ink"
				>
					<p data-testid="sellos-duplicate-name" class="font-medium">
						{{ match.visible ? match.client_name : "A client of another agent" }}
					</p>
					<p class="text-ink-muted">
						Same {{ match.matched_on.map(matchLabel).join(" and ") }}.
						<span data-testid="sellos-duplicate-phone">{{ match.phone }}</span>
					</p>
					<ul v-if="match.leads.length" class="mt-1">
						<li
							v-for="lead in match.leads"
							:key="lead.name"
							data-testid="sellos-duplicate-lead"
						>
							{{ lead.lead_title }}
						</li>
					</ul>
					<p v-if="!match.can_add" class="mt-1 text-ink-muted">
						You cannot see this client. Ask a Company Admin to look at it.
					</p>
					<button
						v-else
						type="button"
						class="btn mt-2"
						data-testid="sellos-duplicate-add"
						@click="addToExisting(match)"
					>
						Add this enquiry to {{ match.client_name }}
					</button>
				</div>
				<button
					type="button"
					class="btn"
					data-testid="sellos-duplicate-new"
					@click="create(true)"
				>
					Save as a new client anyway
				</button>
			</section>
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
		<form
			class="mt-4 flex flex-wrap gap-2 rounded-input border border-line bg-surface p-3"
			data-testid="sellos-leads-filters"
			@submit.prevent="load"
		>
			<input
				v-model.number="filters.budget_min"
				data-testid="sellos-leads-filter-budget-min"
				type="number"
				min="0"
				placeholder="Budget from (rupees)"
				class="field w-auto"
			/>
			<input
				v-model.number="filters.budget_max"
				data-testid="sellos-leads-filter-budget-max"
				type="number"
				min="0"
				placeholder="Budget to (rupees)"
				class="field w-auto"
			/>
			<select
				v-model="filters.configuration"
				data-testid="sellos-leads-filter-configuration"
				class="field w-auto"
			>
				<option value="">Any configuration</option>
				<option v-for="c in CONFIGURATIONS" :key="c">{{ c }}</option>
			</select>
			<input
				v-model="filters.locality"
				data-testid="sellos-leads-filter-locality"
				placeholder="Locality"
				class="field w-auto"
			/>
			<select
				v-model="filters.timeline"
				data-testid="sellos-leads-filter-timeline"
				class="field w-auto"
			>
				<option value="">Any timeline</option>
				<option v-for="t in TIMELINES" :key="t">{{ t }}</option>
			</select>
			<button type="submit" class="btn" data-testid="sellos-leads-filter-apply">
				Filter
			</button>
			<button
				type="button"
				class="btn"
				data-testid="sellos-leads-filter-clear"
				@click="clearFilters"
			>
				Clear filters
			</button>
		</form>
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

import { CLIENT_TYPES, CONFIGURATIONS, TIMELINES, crmApi, serverMessage } from "../crm/crmApi";
import { logRequestError } from "../api";

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
const emptyFilters = () => ({
	budget_min: "",
	budget_max: "",
	configuration: "",
	locality: "",
	timeline: "",
});
const filters = reactive(emptyFilters());
const form = reactive({
	client_name: "",
	client_type: "Buyer",
	phone: "",
	overseas_phone: "",
	country_of_residence: "",
	email: "",
	source: "",
});

function activeFilters() {
	return Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== "" && v != null));
}

async function clearFilters() {
	Object.assign(filters, emptyFilters());
	await load();
}

async function load() {
	loading.value = true;
	loadError.value = "";
	try {
		leads.value = (await crmApi.listLeads(search.value, 0, activeFilters())) || [];
	} catch (e) {
		leads.value = [];
		loadError.value = serverMessage(e, "The leads could not be loaded.");
		logRequestError("list_leads failed", e);
	} finally {
		loading.value = false;
	}
}

const duplicates = ref([]);
const MATCH_LABELS = { phone: "phone number", overseas_phone: "overseas phone", email: "email" };
const matchLabel = (reason) => MATCH_LABELS[reason] || reason;

// Finish a lead on the client it was made for (SOS-P1-16), then show it.
async function finish(clientName, source) {
	const saved = await crmApi.saveLead({ client: clientName, source: source });
	creating.value = false;
	duplicates.value = [];
	Object.assign(form, { client_name: "", phone: "", overseas_phone: "", email: "", source: "" });
	await load();
	router.push(`${basePath.value}/${saved.lead.name}`);
}

// The first save looks for a client with the same phone, overseas phone or email and shows it. The
// agent then adds the enquiry to that client, or saves a new one anyway (SOS-P1-16).
async function create(anyway = false) {
	error.value = "";
	try {
		if (!anyway) {
			duplicates.value =
				(await crmApi.findDuplicates({
					phone: form.phone,
					overseas_phone: form.overseas_phone,
					email: form.email,
				})) || [];
			if (duplicates.value.length) return;
		}
		const { source, ...clientValues } = form;
		const client = await crmApi.saveClient(clientValues);
		await finish(client.name, source);
	} catch (e) {
		error.value = serverMessage(e, "The lead could not be saved.");
	}
}

async function addToExisting(match) {
	error.value = "";
	try {
		await finish(match.name, form.source);
	} catch (e) {
		error.value = serverMessage(e, "The lead could not be saved.");
	}
}

onMounted(load);
</script>
