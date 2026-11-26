<template>
	<PageTemplate data-testid="sellos-tenants-page">
		<template #header>
			<PageHeader
				title="Companies"
				text="Every company has its own site. A new company starts as Requested, then moves to Provisioning, then Active, or Failed. A failed company can be tried again."
				icon="lucide-building-2"
			>
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-tenant-new"
					@click="openCreate"
				>
					<template #prefix
						><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
					/></template>
					Add company
				</AppButton>
			</PageHeader>
		</template>

		<template #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-tenant-stats" />
		</template>

		<template #filters>
			<FilterBar
				v-model:search="search"
				search-label="Search companies"
				search-placeholder="Search companies"
				search-testid="sellos-tenants-search"
				clear-testid="sellos-tenants-filter-clear"
				:active="Boolean(search || statusFilter)"
				:chips="chips"
				data-testid="sellos-tenants-filters"
				@clear="clearFilters"
				@remove-chip="removeChip"
			>
				<FormField
					v-model="statusFilter"
					compact
					type="select"
					label="Status"
					:options="statusOptions"
					data-testid="sellos-tenants-filter-status"
				/>
			</FilterBar>
		</template>

		<FormDrawer
			:open="creating"
			title="Add a company"
			text="The company gets its own site and its own database."
			submit-label="Create company"
			testid="sellos-tenant-form"
			submit-testid="sellos-tenant-create"
			@close="creating = false"
			@submit="create"
		>
			<FormSection title="Company">
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
			</FormSection>
			<p v-if="error" data-testid="sellos-tenant-error" role="alert" class="ui-text-error">
				{{ error }}
			</p>
		</FormDrawer>

		<p
			v-if="error && !creating"
			data-testid="sellos-tenant-error"
			role="alert"
			class="mb-ui-md ui-text-error"
		>
			{{ error }}
		</p>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-tenant-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<DataTable
			v-else
			title="Companies"
			caption="Companies"
			:columns="columns"
			:rows="shown"
			:actions="rowActions"
			:loading="loading"
			loading-label="Loading companies."
			empty-title="No company has been requested yet"
			empty-text="Add the first company with Add company."
			empty-icon="lucide-building-2"
			testid="sellos-tenant-list"
			row-testid="sellos-tenant-row"
			empty-testid="sellos-tenant-empty"
		>
			<template #cell-company_name="{ row }">
				<NameCell
					:name="row.company_name"
					:identifier="row.site_name"
					data-testid="sellos-tenant-name"
				/>
			</template>
			<template #cell-site_name="{ row }">
				<CellText :value="row.site_name" />
			</template>
			<template #cell-admin_email="{ row }">
				<CellText :value="row.admin_email" />
			</template>
			<template #cell-plan="{ row }">
				<CellText :value="row.plan" />
			</template>
			<template #cell-status="{ row }">
				<StatusBadge
					:label="row.status"
					:tone="STATUS_TONE[row.status] || 'neutral'"
					data-testid="sellos-tenant-status"
				/>
			</template>
		</DataTable>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import CellText from "../components/CellText.vue";
import NameCell from "../components/NameCell.vue";
import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import FilterBar from "../components/FilterBar.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import StatusBadge from "../components/StatusBadge.vue";

import { serverMessage } from "../crm/crmApi";
import { logRequestError } from "../api";
import { NEXT_STATUSES, controlApi } from "../control/controlApi";

const tenants = ref([]);
const plans = ref([]);
const loading = ref(true);
const loadError = ref("");
const error = ref("");
const creating = ref(false);
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
const kpis = computed(() => [
	{
		label: "Requested",
		value: countOf("Requested"),
		caption: "waiting to be set up",
		icon: "lucide-inbox",
		tone: "info",
	},
	{
		label: "Provisioning",
		value: countOf("Provisioning"),
		caption: "being built",
		icon: "lucide-loader",
		tone: "warning",
	},
	{
		label: "Active",
		value: countOf("Active"),
		caption: "live companies",
		icon: "lucide-circle-check",
		tone: "success",
	},
	{
		label: "Failed",
		value: countOf("Failed"),
		caption: "can be tried again",
		icon: "lucide-circle-alert",
		tone: "danger",
	},
]);
const search = ref("");
const statusFilter = ref("");
const statusOptions = computed(() => [
	{ label: "All", value: "" },
	...[...new Set(tenants.value.map((r) => r.status).filter(Boolean))].map((v) => ({
		label: v,
		value: v,
	})),
]);
const shown = computed(() => {
	const q = search.value.trim().toLowerCase();
	return tenants.value.filter(
		(r) =>
			(!q ||
				`${r.company_name} ${r.site_name || ""} ${r.admin_email || ""}`
					.toLowerCase()
					.includes(q)) &&
			(!statusFilter.value || r.status === statusFilter.value)
	);
});
const chips = computed(() => [
	...(search.value ? [{ key: "search", label: `Search: ${search.value}` }] : []),
	...(statusFilter.value ? [{ key: "status", label: statusFilter.value }] : []),
]);
function clearFilters() {
	search.value = "";
	statusFilter.value = "";
}
function removeChip(key) {
	if (key === "search") search.value = "";
	else statusFilter.value = "";
}

const columns = [
	{ key: "company_name", label: "Company", primary: true, sortable: true },
	{ key: "site_name", label: "Site", sortable: true },
	{ key: "admin_email", label: "Admin email", sortable: true },
	{ key: "plan", label: "Plan", sortable: true },
	{ key: "status", label: "Status", sortable: true },
];
function openCreate() {
	error.value = "";
	creating.value = true;
}
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
		creating.value = false;
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

// Every row action is in the row menu (docs/DESIGN_SYSTEM.md, "Lists", rule c).
const rowActions = (row) =>
	(NEXT_STATUSES[row.status] || []).map((next) => ({
		label: `Move to ${next}`,
		onClick: () => move(row, next),
	}));

onMounted(load);
</script>
