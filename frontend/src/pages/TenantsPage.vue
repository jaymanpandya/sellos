<template>
	<div class="max-w-4xl" data-testid="sellos-tenants-page">
		<h1 class="text-2xl font-semibold text-ink">Companies</h1>
		<p class="mt-2 text-ink-muted">
			Every company has its own site. A new company starts as Requested, then moves to
			Provisioning, then Active, or Failed. A failed company can be tried again.
		</p>

		<form
			class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4"
			data-testid="sellos-tenant-form"
			@submit.prevent="create"
		>
			<input
				v-model="form.tenant_id"
				required
				pattern="[a-z0-9]+"
				data-testid="sellos-tenant-id"
				class="field"
				placeholder="Tenant ID (lower case letters and digits)"
				aria-label="Tenant ID"
			/>
			<input
				v-model="form.company_name"
				required
				data-testid="sellos-tenant-company"
				class="field"
				placeholder="Company name"
				aria-label="Company name"
			/>
			<input
				v-model="form.admin_email"
				required
				type="email"
				data-testid="sellos-tenant-email"
				class="field"
				placeholder="Admin email"
				aria-label="Admin email"
			/>
			<select
				v-model="form.plan"
				data-testid="sellos-tenant-plan"
				class="field"
				aria-label="Plan"
			>
				<option value="">No plan yet</option>
				<option v-for="p in plans" :key="p.name" :value="p.name">{{ p.name }}</option>
			</select>
			<p
				v-if="error"
				data-testid="sellos-tenant-error"
				role="alert"
				class="text-sm text-accent"
			>
				{{ error }}
			</p>
			<button type="submit" class="btn" data-testid="sellos-tenant-create">
				Create company
			</button>
		</form>

		<p
			v-if="loadError"
			data-testid="sellos-tenant-load-error"
			role="alert"
			class="mt-4 text-accent"
		>
			{{ loadError }}
		</p>
		<p v-else-if="loading" class="mt-4 text-ink-muted">Loading.</p>
		<p
			v-else-if="!tenants.length"
			data-testid="sellos-tenant-empty"
			class="mt-4 text-ink-muted"
		>
			No company has been requested yet.
		</p>
		<ul class="mt-4 divide-y divide-line rounded-input border border-line bg-surface">
			<li
				v-for="t in tenants"
				:key="t.name"
				data-testid="sellos-tenant-row"
				class="flex items-center justify-between gap-3 px-4 py-3"
			>
				<span>
					<span class="block font-medium text-ink" data-testid="sellos-tenant-name">
						{{ t.company_name }}
					</span>
					<span class="block text-sm text-ink-muted">
						{{ t.site_name }} · {{ t.admin_email
						}}<span v-if="t.plan"> · {{ t.plan }}</span>
					</span>
				</span>
				<span class="flex items-center gap-2">
					<span
						data-testid="sellos-tenant-status"
						class="rounded-input bg-brand-light px-2 py-1 text-xs text-ink"
					>
						{{ t.status }}
					</span>
					<button
						v-for="next in NEXT_STATUSES[t.status] || []"
						:key="next"
						type="button"
						class="rounded-input px-3 py-1 text-sm text-ink-muted hover:bg-brand-light"
						:data-testid="`sellos-tenant-to-${next.toLowerCase()}`"
						@click="move(t, next)"
					>
						Move to {{ next }}
					</button>
				</span>
			</li>
		</ul>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import { serverMessage } from "../crm/crmApi";
import { NEXT_STATUSES, controlApi } from "../control/controlApi";

const tenants = ref([]);
const plans = ref([]);
const loading = ref(true);
const loadError = ref("");
const error = ref("");
const form = reactive({ tenant_id: "", company_name: "", admin_email: "", plan: "" });

async function load() {
	loadError.value = "";
	try {
		[tenants.value, plans.value] = await Promise.all([
			controlApi.tenants(),
			controlApi.plans(),
		]);
	} catch (e) {
		loadError.value = serverMessage(e, "Companies could not be loaded.");
		console.error("tenants failed", e);
	} finally {
		loading.value = false;
	}
}

async function create() {
	error.value = "";
	try {
		const values = { ...form };
		if (!values.plan) delete values.plan;
		await controlApi.createTenant(values);
		Object.assign(form, { tenant_id: "", company_name: "", admin_email: "", plan: "" });
		await load();
	} catch (e) {
		error.value = serverMessage(e, "The company could not be created.");
	}
}

async function move(tenant, status) {
	error.value = "";
	try {
		await controlApi.setTenantStatus(tenant.name, status);
		await load();
	} catch (e) {
		error.value = serverMessage(e, "The status could not be changed.");
	}
}

onMounted(load);
</script>
