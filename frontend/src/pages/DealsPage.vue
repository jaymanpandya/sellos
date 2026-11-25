<template>
	<PageTemplate data-testid="sellos-deals-page">
		<template #header>
			<PageHeader
				title="Deals"
				text="A client, a unit or a property and a price, with the commission split among agent, partner and company."
				icon="lucide-handshake"
			>
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-deal-new"
					@click="openForm"
				>
					<template #prefix
						><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
					/></template>
					Record a deal
				</AppButton>
			</PageHeader>
		</template>

		<template v-if="!loadError" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-deal-stats" />
		</template>

		<template #filters>
			<FilterBar
				v-model:search="search"
				search-label="Search deals"
				search-placeholder="Search deals"
				search-testid="sellos-deal-search"
				clear-testid="sellos-deal-filter-clear"
				:active="Boolean(search || statusFilter)"
				:chips="chips"
				data-testid="sellos-deal-filters"
				@clear="clearFilters"
				@remove-chip="removeChip"
			>
				<FormField
					v-model="statusFilter"
					compact
					type="select"
					label="Status"
					:options="statusOptions"
					data-testid="sellos-deal-filter-status"
				/>
			</FilterBar>
		</template>

		<p
			v-if="error && !creating"
			role="alert"
			data-testid="sellos-deal-error"
			class="mb-ui-md ui-text-error"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-deal-notice"
			class="mb-ui-md ui-text-small"
		>
			{{ notice }}
		</p>
		<LoadError
			v-if="loadError"
			:message="loadError"
			class="mb-ui-md"
			data-testid="sellos-deal-load-error"
			@retry="load"
		/>

		<DataTable
			v-if="!loadError"
			title="All deals"
			caption="Deals"
			:columns="columns"
			:rows="shown"
			:row-to="(row) => `/crm/deals/${row.name}`"
			:loading="!loaded"
			loading-label="Loading deals."
			:row-name="(row) => row.client_name"
			:row-attrs="rowAttrs"
			empty-title="No deals yet"
			empty-text="Record the first deal to split its commission."
			empty-icon="lucide-handshake"
			testid="sellos-deal-list"
			row-testid="sellos-deal-row"
			loading-testid="sellos-deal-loading"
			empty-testid="sellos-deal-empty"
		>
			<template #cell-client_name="{ row }">
				<span class="block" data-testid="sellos-deal-title"
					>{{ row.client_name }}, {{ row.target }}</span
				>
			</template>
			<template #cell-approval_status="{ row }">
				<StatusBadge
					:tone="row.approval_status === 'Approved' ? 'success' : 'warning'"
					:label="row.approval_status"
					data-testid="sellos-deal-status"
				/>
			</template>
			<template #cell-price="{ row }">
				<span class="tabular-nums" data-testid="sellos-deal-money">{{
					formatMoney(row.price)
				}}</span>
			</template>
			<template #cell-commission_amount="{ row }">
				<span class="tabular-nums">{{ formatMoney(row.commission_amount) }}</span>
			</template>
			<template #cell-splits="{ row }">
				<ul class="space-y-1" data-testid="sellos-deal-splits">
					<li
						v-for="(s, n) in row.splits"
						:key="n"
						data-testid="sellos-deal-split"
						:data-party="s.party_type"
						class="ui-text-small"
					>
						{{ s.party_type }}: {{ s.party }}, {{ s.percent }}% ({{
							formatMoney(s.amount)
						}})
					</li>
				</ul>
			</template>
			<template #cell-approval="{ row }">
				<p
					v-if="row.approval_status === 'Approved'"
					class="mb-ui-sm ui-text-muted"
					data-testid="sellos-deal-approved"
				>
					Approved by {{ row.approved_by_name }} on
					{{ formatDateTime(row.approved_on) }}. The split is kept unless it is reopened.
				</p>
				<AppButton
					v-if="row.approval_status !== 'Approved'"
					type="button"
					variant="primary"
					data-testid="sellos-deal-approve"
					@click="approve(row)"
				>
					Approve the split
				</AppButton>
				<AppButton
					v-else
					type="button"
					data-testid="sellos-deal-reopen"
					@click="reopen(row)"
				>
					Reopen the split
				</AppButton>
			</template>
		</DataTable>

		<!-- Recording a deal is a drawer: nothing is an open form under the list. -->
		<FormDrawer
			:open="creating"
			title="Record a deal"
			text="The shares of the commission split must add up to 100 percent."
			submit-label="Record deal"
			testid="sellos-deal-form"
			submit-testid="sellos-deal-save"
			@close="closeForm"
			@submit="save"
		>
			<FormSection title="Deal">
				<FormField
					v-model="form.client"
					type="select"
					label="Client"
					:options="clientOptions"
					required
					data-testid="sellos-deal-client"
				/>
				<FormField
					v-model="form.unit"
					type="select"
					label="Unit"
					:options="unitOptions"
					hint="Choose a unit or a property, not both."
					data-testid="sellos-deal-unit"
				/>
				<FormField
					v-model="form.property"
					type="select"
					label="Property"
					:options="propertyOptions"
					data-testid="sellos-deal-property"
				/>
				<MoneyField
					v-model="form.price"
					label="Price (Rs)"
					required
					data-testid="sellos-deal-price"
				/>
				<MoneyField
					v-model="form.commission_amount"
					label="Commission (Rs)"
					data-testid="sellos-deal-commission"
				/>
			</FormSection>
			<FormSection title="Commission split">
				<p class="md:col-span-2 ui-text-muted">
					Leave a share empty to leave that party out. The shares must add up to 100.
				</p>
				<FormField
					v-model="form.agent"
					type="select"
					label="Agent"
					:options="agentOptions"
					data-testid="sellos-deal-agent"
				/>
				<FormField
					v-model="form.agent_percent"
					type="number"
					label="Agent share (%)"
					data-testid="sellos-deal-agent-percent"
				/>
				<FormField
					v-model="form.firm"
					type="select"
					label="Channel partner firm"
					:options="firmOptions"
					data-testid="sellos-deal-firm"
				/>
				<FormField
					v-model="form.firm_percent"
					type="number"
					label="Channel partner share (%)"
					data-testid="sellos-deal-firm-percent"
				/>
				<FormField
					v-model="form.company_percent"
					type="number"
					label="Company share (%)"
					data-testid="sellos-deal-company-percent"
				/>
				<p
					class="md:col-span-2 ui-text-small"
					:class="total === 100 ? 'ui-text-body' : 'ui-text-error'"
					data-testid="sellos-deal-total"
				>
					The split adds up to {{ total }} percent.
				</p>
			</FormSection>
			<p v-if="error" role="alert" data-testid="sellos-deal-error" class="ui-text-error">
				{{ error }}
			</p>
		</FormDrawer>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import FilterBar from "../components/FilterBar.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import MoneyField from "../components/MoneyField.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { dealApi } from "../crm/dealsApi";
import { formatDateTime, formatMoney } from "../format";

// Deals (SOS-P4-06). Every change is made on the server and the list read back. The server checks that the
// shares add up to 100, so the total shown here only helps the person typing.
const deals = ref([]);
const options = reactive({ clients: [], units: [], properties: [], agents: [], firms: [] });
const blank = () => ({
	client: "",
	unit: "",
	property: "",
	price: "",
	commission_amount: "",
	agent: "",
	agent_percent: "",
	firm: "",
	firm_percent: "",
	company_percent: "",
});
const form = reactive(blank());
const error = ref("");
const notice = ref("");
const loadError = ref("");
const loaded = ref(false);

const search = ref("");
const statusFilter = ref("");
const statusOptions = [
	{ label: "All statuses", value: "" },
	{ label: "Approved", value: "Approved" },
	{ label: "Pending approval", value: "Pending approval" },
];
const shown = computed(() => {
	const q = search.value.trim().toLowerCase();
	return deals.value.filter(
		(r) =>
			(!q || `${r.client_name} ${r.target}`.toLowerCase().includes(q)) &&
			(!statusFilter.value || r.approval_status === statusFilter.value)
	);
});
const chips = computed(() => [
	...(search.value ? [{ key: "search", label: `Search: ${search.value}` }] : []),
	...(statusFilter.value ? [{ key: "status", label: `${statusFilter.value}` }] : []),
]);
function clearFilters() {
	search.value = "";
	statusFilter.value = "";
}
function removeChip(key) {
	if (key === "search") search.value = "";
	else statusFilter.value = "";
}

const creating = ref(false);

const kpis = computed(() => {
	const rows = deals.value;
	return [
		{
			label: "Deals",
			value: rows.length,
			caption: "recorded so far",
			icon: "lucide-handshake",
		},
		{
			label: "Pending approval",
			value: rows.filter((d) => d.approval_status !== "Approved").length,
			caption: "splits waiting for a Company Admin",
			icon: "lucide-clock",
			tone: "warning",
		},
		{
			label: "Approved",
			value: rows.filter((d) => d.approval_status === "Approved").length,
			caption: "splits settled",
			icon: "lucide-badge-check",
			tone: "success",
		},
		{
			label: "Commission",
			value: formatMoney(rows.reduce((sum, d) => sum + Number(d.commission_amount || 0), 0)),
			caption: "across these deals",
			icon: "lucide-badge-indian-rupee",
		},
	];
});

const columns = [
	{ key: "client_name", label: "Deal", primary: true, sortable: true, wrap: true },
	{ key: "approval_status", label: "Status", sortable: true },
	{
		key: "price",
		label: "Price",
		sortable: true,
		align: "right",
		sortValue: (d) => Number(d.price || 0),
	},
	{
		key: "commission_amount",
		label: "Commission",
		sortable: true,
		align: "right",
		sortValue: (d) => Number(d.commission_amount || 0),
	},
	{ key: "splits", label: "Commission split", wrap: true, class: "min-w-[14rem]" },
	{ key: "approval", label: "Approval", wrap: true, class: "min-w-[14rem]" },
];
const rowAttrs = (d) => ({ "data-client": d.client_name, "data-status": d.approval_status });

function openForm() {
	error.value = "";
	creating.value = true;
}
function closeForm() {
	error.value = "";
	creating.value = false;
}

const choose = (label, list) => [
	{ label, value: "" },
	...list.map((o) => ({ label: o.label, value: o.value })),
];
const clientOptions = computed(() => choose("Choose a client", options.clients));
const unitOptions = computed(() => choose("No unit", options.units));
const propertyOptions = computed(() => choose("No property", options.properties));
const agentOptions = computed(() => choose("No agent", options.agents));
const firmOptions = computed(() => choose("No channel partner", options.firms));

const share = (v) => (v === "" || v == null ? 0 : Number(v));
const total = computed(
	() =>
		Math.round(
			(share(form.agent_percent) + share(form.firm_percent) + share(form.company_percent)) *
				100
		) / 100
);

async function load() {
	loadError.value = "";
	try {
		const result = await dealApi.overview();
		deals.value = result.deals;
		for (const key of Object.keys(options)) options[key] = result[key];
	} catch (e) {
		loadError.value = serverMessage(e, "The deals could not be loaded.");
	} finally {
		loaded.value = true;
	}
}

async function run(action, done, failed) {
	error.value = "";
	notice.value = "";
	try {
		await action();
		notice.value = done;
		await load();
	} catch (e) {
		error.value = serverMessage(e, failed);
	}
}

function splits() {
	const rows = [];
	if (form.agent_percent !== "")
		rows.push({ party_type: "Agent", agent: form.agent, percent: form.agent_percent });
	if (form.firm_percent !== "")
		rows.push({
			party_type: "Channel Partner",
			partner_firm: form.firm,
			percent: form.firm_percent,
		});
	if (form.company_percent !== "")
		rows.push({ party_type: "Company", percent: form.company_percent });
	return rows;
}

const save = () => {
	if (!form.client || !form.price) {
		error.value = "Choose a client and enter the price.";
		return Promise.resolve();
	}
	return run(
		async () => {
			await dealApi.save({
				client: form.client,
				unit: form.unit || null,
				property: form.property || null,
				price: form.price,
				commission_amount: form.commission_amount || 0,
				splits: splits(),
			});
			Object.assign(form, blank());
			creating.value = false;
		},
		"The deal is recorded. Approve its split to settle it.",
		"The deal could not be recorded."
	);
};

const approve = (d) =>
	run(
		() => dealApi.approve(d.name),
		`${d.client_name}: the split is approved.`,
		"The split could not be approved."
	);

const reopen = (d) =>
	run(
		() => dealApi.reopen(d.name),
		`${d.client_name}: the split is reopened and waits for approval.`,
		"The split could not be reopened."
	);

onMounted(load);
</script>
