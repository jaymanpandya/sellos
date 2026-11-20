<template>
	<div data-testid="sellos-tenants-page">
		<PageHeader
			title="Companies"
			text="Every company has its own site. A new company starts as Requested, then moves to Provisioning, then Active, or Failed. A failed company can be tried again."
			icon="lucide-building-2"
		/>

		<div
			class="mb-ui-md grid grid-cols-2 gap-ui-md md:grid-cols-4"
			data-testid="sellos-tenant-stats"
		>
			<StatCard label="Requested" :value="countOf('Requested')" icon="lucide-inbox" />
			<StatCard
				label="Provisioning"
				:value="countOf('Provisioning')"
				icon="lucide-loader"
				tone="warning"
			/>
			<StatCard label="Active" :value="countOf('Active')" icon="lucide-circle-check" />
			<StatCard
				label="Failed"
				:value="countOf('Failed')"
				icon="lucide-circle-alert"
				tone="warning"
			/>
		</div>

		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-tenant-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<LoadingSkeleton v-else-if="loading" />
		<ListCard v-else title="Companies" data-testid="sellos-tenant-list">
			<EmptyState
				v-if="!tenants.length"
				title="No company has been requested yet"
				text="Add the first company below."
				icon="lucide-building-2"
				data-testid="sellos-tenant-empty"
			/>
			<ul class="space-y-ui-sm">
				<li
					v-for="t in tenants"
					:key="t.name"
					data-testid="sellos-tenant-row"
					class="flex flex-wrap items-center justify-between gap-3 rounded-input border border-line-soft p-ui-md"
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
					<span class="flex flex-wrap items-center gap-2">
						<StatusBadge
							:label="t.status"
							:tone="STATUS_TONE[t.status] || 'neutral'"
							data-testid="sellos-tenant-status"
						/>
						<AppButton
							v-for="next in NEXT_STATUSES[t.status] || []"
							:key="next"
							type="button"
							:data-testid="`sellos-tenant-to-${next.toLowerCase()}`"
							@click="move(t, next)"
						>
							Move to {{ next }}
						</AppButton>
					</span>
				</li>
			</ul>
		</ListCard>

		<form class="ui-card mt-ui-md" data-testid="sellos-tenant-form" @submit.prevent="create">
			<h2 class="ui-card-heading mb-ui-md">Add a company</h2>
			<div class="grid grid-cols-1 gap-x-ui-md gap-y-ui-md md:grid-cols-2">
				<FormField
					v-model="form.tenant_id"
					label="Tenant ID"
					hint="Lower case letters and digits."
					required
					pattern="[a-z0-9]+"
					data-testid="sellos-tenant-id"
				/>
				<FormField
					v-model="form.company_name"
					label="Company name"
					required
					data-testid="sellos-tenant-company"
				/>
				<FormField
					v-model="form.admin_email"
					type="email"
					label="Admin email"
					required
					data-testid="sellos-tenant-email"
				/>
				<FormField
					v-model="form.plan"
					type="select"
					label="Plan"
					:options="planOptions"
					data-testid="sellos-tenant-plan"
				/>
			</div>
			<p
				v-if="error"
				data-testid="sellos-tenant-error"
				role="alert"
				class="mt-ui-md text-sm text-accent"
			>
				{{ error }}
			</p>
			<div class="mt-ui-md">
				<AppButton type="submit" variant="primary" data-testid="sellos-tenant-create">
					Create company
				</AppButton>
			</div>
		</form>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import StatCard from "../components/StatCard.vue";
import StatusBadge from "../components/StatusBadge.vue";

import { serverMessage } from "../crm/crmApi";
import { logRequestError } from "../api";
import { NEXT_STATUSES, controlApi } from "../control/controlApi";

const tenants = ref([]);
const plans = ref([]);
const loading = ref(true);
const loadError = ref("");
const error = ref("");
const STATUS_TONE = {
	Requested: "info",
	Provisioning: "warning",
	Active: "success",
	Failed: "danger",
};
const planOptions = computed(() => [
	{ label: "No plan yet", value: "" },
	...plans.value.map((p) => ({ label: p.name, value: p.name })),
]);
const countOf = (status) => tenants.value.filter((t) => t.status === status).length;
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
		logRequestError("tenants failed", e);
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
