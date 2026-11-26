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
			<PageTabs
				v-model="period"
				:tabs="periodTabs"
				label="Period"
				data-testid="sellos-deal-period"
			/>
			<p class="mb-ui-md ui-text-muted" data-testid="sellos-deal-period-dates">
				{{ periodDates }}
			</p>
			<KpiStrip :items="kpis" data-testid="sellos-deal-stats" />
		</template>

		<template #filters>
			<FilterBar
				v-model:search="search"
				search-label="Search deals"
				search-placeholder="Search deals"
				search-testid="sellos-deal-search"
				clear-testid="sellos-deal-filter-clear"
				:active="Boolean(search || statusFilter || splitFilter || partnerFilter)"
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
				<FormField
					v-model="splitFilter"
					compact
					type="select"
					label="Commission split"
					:options="splitOptions"
					data-testid="sellos-deal-filter-split"
				/>
				<FormField
					v-model="partnerFilter"
					compact
					type="select"
					label="Channel partner"
					:options="partnerFilterOptions"
					data-testid="sellos-deal-filter-partner"
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

		<p
			v-if="bulkNotice"
			role="status"
			class="mb-ui-md ui-text-small"
			data-testid="sellos-deal-bulk-result"
		>
			{{ bulkNotice }}
		</p>
		<!-- The bulk bar exists only while rows are selected. -->
		<BulkBar :count="selected.length" @clear="selected = []">
			<AppButton
				type="button"
				variant="primary"
				:disabled="!selected.length"
				data-testid="sellos-deal-bulk-approve"
				@click="bulkApprove"
			>
				Approve selected splits
			</AppButton>
		</BulkBar>

		<DataTable
			v-if="!loadError"
			v-model:selected="selected"
			selectable
			:actions="rowActions"
			select-testid="sellos-deal-select"
			select-all-testid="sellos-deal-select-all"
			title="All deals"
			dense
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
				<span class="block" data-testid="sellos-deal-title">{{ row.client_name }}</span>
				<span class="block ui-text-muted ui-text-small">{{ row.target }}</span>
			</template>
			<template #cell-has_commission_split="{ row }">
				<span data-testid="sellos-deal-has-split">{{
					row.has_commission_split ? "Yes" : "No"
				}}</span>
			</template>
			<template v-for="n in 3" :key="n" #[`cell-split${n}`]="{ row }">
				<template v-if="row.partner_splits[n - 1]">
					<span
						class="block"
						data-testid="sellos-deal-split"
						data-party="Channel Partner"
						>{{ row.partner_splits[n - 1].party }}</span
					>
					<span class="block ui-text-muted ui-text-small tabular-nums"
						>{{ row.partner_splits[n - 1].percent }}% ·
						{{ formatBudget(row.partner_splits[n - 1].amount) }}</span
					>
				</template>
				<span v-else class="ui-text-muted">-</span>
			</template>
			<template #cell-agent_share="{ row }">
				<span class="block tabular-nums" data-testid="sellos-deal-split" data-party="Agent"
					>{{ row.agent_share.percent }}%</span
				>
				<span class="block ui-text-muted ui-text-small tabular-nums">{{
					formatBudget(row.agent_share.amount)
				}}</span>
			</template>
			<template #cell-company_share="{ row }">
				<span
					class="block tabular-nums"
					data-testid="sellos-deal-split"
					data-party="Company"
					>{{ row.company_share.percent }}%</span
				>
				<span class="block ui-text-muted ui-text-small tabular-nums">{{
					formatBudget(row.company_share.amount)
				}}</span>
			</template>
			<template #cell-commission_amount="{ row }">
				<span class="tabular-nums" data-testid="sellos-deal-money">{{
					formatBudget(row.commission_amount)
				}}</span>
			</template>
			<template #cell-approval_status="{ row }">
				<StatusBadge
					:tone="row.approval_status === 'Approved' ? 'success' : 'warning'"
					:label="row.approval_status"
					data-testid="sellos-deal-status"
				/>
			</template>
			<template #cell-approval="{ row }">
				<p
					v-if="row.approval_status === 'Approved'"
					class="mb-ui-sm ui-text-muted ui-text-small"
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
					@click.stop="approve(row)"
				>
					Approve
				</AppButton>
				<AppButton
					v-else
					type="button"
					data-testid="sellos-deal-reopen"
					@click.stop="reopen(row)"
				>
					Reopen
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
				<template v-for="(partner, i) in form.partners" :key="i">
					<FormField
						v-model="partner.firm"
						type="select"
						:label="i ? `Channel partner firm ${i + 1}` : 'Channel partner firm'"
						:options="firmOptions"
						:data-testid="i ? `sellos-deal-firm-${i + 1}` : 'sellos-deal-firm'"
					/>
					<FormField
						v-model="partner.percent"
						type="number"
						:label="
							i ? `Channel partner share ${i + 1} (%)` : 'Channel partner share (%)'
						"
						:data-testid="
							i ? `sellos-deal-firm-percent-${i + 1}` : 'sellos-deal-firm-percent'
						"
					/>
				</template>
				<div v-if="form.partners.length < 3" class="md:col-span-2">
					<AppButton
						type="button"
						data-testid="sellos-deal-add-partner"
						@click="form.partners.push({ firm: '', percent: '' })"
					>
						Add another channel partner
					</AppButton>
				</div>
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
import { computed, onMounted, reactive, ref, watch } from "vue";

import AppButton from "../components/AppButton.vue";
import BulkBar from "../components/BulkBar.vue";
import DataTable from "../components/DataTable.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import FilterBar from "../components/FilterBar.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import MoneyField from "../components/MoneyField.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTabs from "../components/PageTabs.vue";
import PageTemplate from "../components/PageTemplate.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { useRouter } from "vue-router";
import { serverMessage } from "../crm/crmApi";
import { dealApi } from "../crm/dealsApi";
import { formatBudget, formatDate, formatDateTime } from "../format";

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
	partners: [{ firm: "", percent: "" }],
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
const splitFilter = ref("");
const partnerFilter = ref("");
const splitOptions = [
	{ label: "Any", value: "" },
	{ label: "With a channel partner", value: "yes" },
	{ label: "No channel partner", value: "no" },
];
const partnerFilterOptions = computed(() => [
	{ label: "Any partner", value: "" },
	...[...new Set(deals.value.flatMap((d) => d.partner_splits.map((p) => p.party)))]
		.sort()
		.map((p) => ({ label: p, value: p })),
]);
const shown = computed(() => {
	const q = search.value.trim().toLowerCase();
	return deals.value.filter(
		(r) =>
			(!q || `${r.client_name} ${r.target}`.toLowerCase().includes(q)) &&
			(!statusFilter.value || r.approval_status === statusFilter.value) &&
			(!splitFilter.value ||
				(splitFilter.value === "yes") === Boolean(r.has_commission_split)) &&
			(!partnerFilter.value || r.partner_splits.some((p) => p.party === partnerFilter.value))
	);
});
const chips = computed(() => [
	...(search.value ? [{ key: "search", label: `Search: ${search.value}` }] : []),
	...(statusFilter.value ? [{ key: "status", label: `${statusFilter.value}` }] : []),
	...(splitFilter.value
		? [
				{
					key: "split",
					label:
						splitFilter.value === "yes"
							? "With a channel partner"
							: "No channel partner",
				},
		  ]
		: []),
	...(partnerFilter.value ? [{ key: "partner", label: `Partner: ${partnerFilter.value}` }] : []),
]);
function clearFilters() {
	search.value = statusFilter.value = splitFilter.value = partnerFilter.value = "";
}
function removeChip(key) {
	const refs = { search, status: statusFilter, split: splitFilter, partner: partnerFilter };
	refs[key].value = "";
}

// Rows can be selected: the bulk bar approves the splits of the selected deals that wait for approval.
const selected = ref([]);
const bulkNotice = ref("");
async function bulkApprove() {
	error.value = "";
	bulkNotice.value = "";
	const waiting = deals.value.filter(
		(d) => selected.value.includes(d.name) && d.approval_status !== "Approved"
	);
	let done = 0;
	try {
		for (const d of waiting) {
			await dealApi.approve(d.name);
			done += 1;
		}
	} catch (e) {
		error.value = serverMessage(e, "A split could not be approved.");
	}
	bulkNotice.value = `${done} of ${waiting.length} splits approved.`;
	selected.value = [];
	await load();
}
const rowActions = (d) => [
	{ label: "Open deal", onClick: () => router.push(`/crm/deals/${d.name}`) },
	d.approval_status === "Approved"
		? { label: "Reopen the split", onClick: () => reopen(d) }
		: { label: "Approve the split", onClick: () => approve(d) },
];

const router = useRouter();
const creating = ref(false);

// The period (Month to date unless changed) limits the cards and the list, on the server.
const periodTabs = [
	{ key: "day", label: "Day to date" },
	{ key: "week", label: "Week to date" },
	{ key: "month", label: "Month to date" },
	{ key: "year", label: "Year to date" },
];
const period = ref("month");
const periodInfo = ref({ label: "", start: "", end: "" });
const totals = ref({ total_commission: 0, partner_payout: 0, company_share: 0, count: 0 });
const periodLabel = computed(() => periodInfo.value.label.toLowerCase());
const periodDates = computed(() => {
	const { start, end } = periodInfo.value;
	if (!start) return "";
	return start === end ? formatDate(start) : `${formatDate(start)} to ${formatDate(end)}`;
});

const kpis = computed(() => [
	{
		label: "Total commission",
		value: formatBudget(totals.value.total_commission),
		caption: period.value === "all" ? "all deals" : periodLabel.value,
		icon: "lucide-badge-indian-rupee",
	},
	{
		label: "Channel Partner payout",
		value: formatBudget(totals.value.partner_payout),
		caption: "paid out to partners",
		icon: "lucide-users",
	},
	{
		label: "Company share",
		value: formatBudget(totals.value.company_share),
		caption: "kept by the company",
		icon: "lucide-landmark",
		tone: "success",
	},
	{
		label: "Deals",
		value: totals.value.count,
		caption: "in this period",
		icon: "lucide-handshake",
	},
]);

const amountOf = (d) => Number(d.commission_amount || 0);
const columns = [
	{ key: "client_name", label: "Deal", primary: true, sortable: true, wrap: true },
	{
		key: "has_commission_split",
		label: "Commission split",
		sortable: true,
		sortValue: (d) => d.has_commission_split,
	},
	...[1, 2, 3].map((n) => ({
		key: `split${n}`,
		label: `Split ${n}`,
		wrap: true,
		sortable: true,
		sortValue: (d) => Number(d.partner_splits[n - 1]?.amount || 0),
	})),
	{
		key: "agent_share",
		label: "Agent share",
		sortable: true,
		sortValue: (d) => Number(d.agent_share.amount || 0),
	},
	{
		key: "company_share",
		label: "Company share",
		sortable: true,
		sortValue: (d) => Number(d.company_share.amount || 0),
	},
	{
		key: "commission_amount",
		label: "Total commission",
		sortable: true,
		align: "right",
		sortValue: amountOf,
	},
	{ key: "approval_status", label: "Status", sortable: true },
	{ key: "approval", label: "Approval", wrap: true },
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
			(share(form.agent_percent) +
				form.partners.reduce((sum, p) => sum + share(p.percent), 0) +
				share(form.company_percent)) *
				100
		) / 100
);

async function load() {
	loadError.value = "";
	try {
		const result = await dealApi.overview(0, period.value);
		deals.value = result.deals;
		totals.value = result.totals;
		periodInfo.value = result.period;
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
	for (const p of form.partners)
		if (p.percent !== "")
			rows.push({ party_type: "Channel Partner", partner_firm: p.firm, percent: p.percent });
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

watch(period, load);
onMounted(load);
</script>
