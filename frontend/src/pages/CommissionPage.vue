<template>
	<PageTemplate data-testid="sellos-commission-page">
		<template #header>
			<PageHeader
				title="Commission"
				text="Rates for each project, and what each channel partner is owed from Due to Paid."
				icon="lucide-badge-indian-rupee"
			>
				<AppButton
					type="button"
					data-testid="sellos-commission-export-open"
					@click="openForm('export')"
				>
					Export a statement
				</AppButton>
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-commission-rate-new"
					@click="openForm('rate')"
				>
					<template #prefix
						><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
					/></template>
					Add rate
				</AppButton>
			</PageHeader>
		</template>

		<template v-if="!loadError" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-commission-stats" />
		</template>

		<template #filters>
			<FilterBar
				v-model:search="search"
				search-label="Search payouts"
				search-placeholder="Search payouts"
				search-testid="sellos-commission-search"
				clear-testid="sellos-commission-filter-clear"
				:active="Boolean(search || statusFilter)"
				:chips="chips"
				data-testid="sellos-commission-filters"
				@clear="clearFilters"
				@remove-chip="removeChip"
			>
				<FormField
					v-model="statusFilter"
					compact
					type="select"
					label="Status"
					:options="statusOptions"
					data-testid="sellos-commission-filter-status"
				/>
			</FilterBar>
		</template>

		<p
			v-if="error && !drawer"
			role="alert"
			data-testid="sellos-commission-error"
			class="mb-ui-md ui-text-error"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-commission-notice"
			class="mb-ui-md ui-text-small"
		>
			{{ notice }}
		</p>
		<p
			v-if="exported"
			role="status"
			class="mb-ui-md ui-text-small"
			data-testid="sellos-commission-exported"
		>
			{{ exported }}
		</p>
		<LoadError
			v-if="loadError"
			:message="loadError"
			class="mb-ui-md"
			data-testid="sellos-commission-load-error"
			@retry="load"
		/>

		<SectionCard v-if="waiting.length" title="Deals waiting for a rate" class="mb-ui-md">
			<ul class="space-y-1 ui-text-small" data-testid="sellos-commission-waiting">
				<li v-for="w in waiting" :key="w.deal + w.partner_firm" class="ui-text-body">
					{{ w.deal }}, {{ w.firm_name }}: {{ w.reason }}
				</li>
			</ul>
		</SectionCard>

		<DataTable
			v-if="!loadError"
			title="Payouts"
			caption="Payouts"
			:columns="payoutColumns"
			:rows="shown"
			:loading="!loaded"
			loading-label="Loading payouts."
			:row-name="(row) => row.firm_name"
			:row-attrs="payoutAttrs"
			empty-title="No payouts yet"
			empty-text="A payout is made when a deal with a channel partner share is approved and a rate applies."
			empty-icon="lucide-badge-indian-rupee"
			testid="sellos-commission-payouts"
			row-testid="sellos-commission-payout"
			loading-testid="sellos-commission-payouts-loading"
			empty-testid="sellos-commission-payouts-empty"
		>
			<template #cell-firm_name="{ row }">
				<span class="block">{{ row.firm_name }}</span>
				<span class="block ui-text-muted">{{ row.target }}</span>
			</template>
			<template #cell-status="{ row }">
				<StatusBadge
					:tone="TONES[row.status]"
					:label="row.status"
					data-testid="sellos-commission-payout-status"
				/>
			</template>
			<template #cell-booking_date="{ row }">
				<span class="ui-text-secondary">{{ formatDate(row.booking_date) }}</span>
			</template>
			<template #cell-agreement_value="{ row }">
				<span class="tabular-nums">{{ formatMoney(row.agreement_value, 2) }}</span>
			</template>
			<template #cell-commission_total="{ row }">
				<span class="block tabular-nums">{{ formatMoney(row.commission_total, 2) }}</span>
				<span class="block ui-text-muted">
					{{ row.rate_basis }}, firm's share {{ row.partner_percent }}%
				</span>
			</template>
			<template #cell-commission_due="{ row }">
				<span class="tabular-nums" data-testid="sellos-commission-payout-due">{{
					formatMoney(row.commission_due, 2)
				}}</span>
			</template>
			<template #cell-notes="{ row }">
				<p
					v-if="row.status === 'Paid'"
					class="ui-text-small"
					data-testid="sellos-commission-payout-paid"
				>
					Paid on {{ formatDate(row.paid_on) }}, reference {{ row.payment_reference }}.
				</p>
				<p
					v-if="row.status === 'On hold'"
					class="ui-text-small"
					data-testid="sellos-commission-payout-hold"
				>
					On hold: {{ row.hold_reason }}
				</p>
			</template>
			<template #cell-actions="{ row }">
				<div v-if="row.status !== 'Paid'" class="flex flex-wrap gap-ui-sm">
					<AppButton
						v-if="row.status === 'Due'"
						type="button"
						variant="primary"
						data-testid="sellos-commission-approve"
						@click="move(row, 'Approved')"
					>
						Approve
					</AppButton>
					<AppButton
						v-if="row.status === 'Approved'"
						type="button"
						variant="primary"
						data-testid="sellos-commission-pay"
						@click="openPayout(row, 'pay')"
					>
						Record payment
					</AppButton>
					<AppButton
						v-if="row.status !== 'On hold'"
						type="button"
						data-testid="sellos-commission-hold"
						@click="openPayout(row, 'hold')"
					>
						Put on hold
					</AppButton>
					<AppButton
						v-else
						type="button"
						data-testid="sellos-commission-release"
						@click="move(row, row.held_from || 'Due')"
					>
						Release the hold
					</AppButton>
				</div>
			</template>
		</DataTable>

		<div class="mt-ui-md">
			<DataTable
				v-if="!loadError"
				title="Commission rates"
				caption="Commission rates"
				:columns="rateColumns"
				:rows="rates"
				:loading="!loaded"
				loading-label="Loading rates."
				:row-name="(row) => row.project_name"
				:row-attrs="rateAttrs"
				empty-title="No rates yet"
				empty-text="Add the first rate to start making payouts."
				empty-icon="lucide-percent"
				testid="sellos-commission-rates"
				row-testid="sellos-commission-rate"
				loading-testid="sellos-commission-rates-loading"
				empty-testid="sellos-commission-rates-empty"
			>
				<template #cell-firm_name="{ row }">
					<span class="ui-text-secondary">{{ row.firm_name || "All partners" }}</span>
				</template>
				<template #cell-value="{ row }">
					<span class="tabular-nums">{{
						row.rate_type === "Percentage"
							? `${row.value}%`
							: formatMoney(row.value, 2)
					}}</span>
				</template>
				<template #cell-start_date="{ row }">
					<span class="ui-text-secondary">{{ formatDate(row.start_date) }}</span>
				</template>
				<template #cell-archive="{ row }">
					<AppButton
						type="button"
						data-testid="sellos-commission-rate-archive"
						@click="archive(row)"
					>
						Archive
					</AppButton>
				</template>
			</DataTable>
		</div>

		<!-- Add a rate. -->
		<FormDrawer
			:open="drawer === 'rate'"
			title="Add a rate"
			text="Earlier rates are kept. The rate in force on the booking date applies."
			submit-label="Add the rate"
			testid="sellos-commission-rate-form"
			submit-testid="sellos-commission-save-rate"
			@close="closeForm"
			@submit="saveRate"
		>
			<FormSection title="Rate">
				<FormField
					v-model="form.project"
					type="select"
					label="Project"
					:options="projectOptions"
					required
					data-testid="sellos-commission-project"
				/>
				<FormField
					v-model="form.partner_firm"
					type="select"
					label="Partner firm"
					:options="firmOptions"
					hint="Leave empty for every partner. A firm's own rate overrides the project's."
					data-testid="sellos-commission-firm"
				/>
				<FormField
					v-model="form.rate_type"
					type="select"
					label="Rate type"
					:options="rateTypes"
					required
					data-testid="sellos-commission-rate-type"
				/>
				<FormField
					v-model="form.value"
					type="number"
					label="Rate (percent or rupees)"
					required
					data-testid="sellos-commission-value"
				/>
				<FormField
					v-model="form.start_date"
					type="date"
					label="Starts on"
					required
					data-testid="sellos-commission-start"
				/>
			</FormSection>
			<p
				v-if="error"
				role="alert"
				data-testid="sellos-commission-error"
				class="ui-text-error"
			>
				{{ error }}
			</p>
		</FormDrawer>

		<!-- Record a payment. The server checks the reference and the date. -->
		<FormDrawer
			:open="drawer === 'pay'"
			title="Record a payment"
			:text="activePayout ? `${activePayout.firm_name}, ${activePayout.target}` : ''"
			submit-label="Mark as paid"
			testid="sellos-commission-pay-form"
			submit-testid="sellos-commission-pay-save"
			@close="closeForm"
			@submit="activePayout && pay(activePayout)"
		>
			<FormSection title="Payment">
				<FormField
					v-model="paying.reference"
					type="text"
					label="Payment reference (required)"
					data-testid="sellos-commission-reference"
				/>
				<FormField
					v-model="paying.date"
					type="date"
					label="Paid on (required)"
					data-testid="sellos-commission-paid-on"
				/>
			</FormSection>
			<p
				v-if="error"
				role="alert"
				data-testid="sellos-commission-error"
				class="ui-text-error"
			>
				{{ error }}
			</p>
		</FormDrawer>

		<!-- Put a payout on hold. -->
		<FormDrawer
			:open="drawer === 'hold'"
			title="Put on hold"
			:text="activePayout ? `${activePayout.firm_name}, ${activePayout.target}` : ''"
			submit-label="Put on hold"
			testid="sellos-commission-hold-form"
			submit-testid="sellos-commission-hold-save"
			@close="closeForm"
			@submit="activePayout && hold(activePayout)"
		>
			<FormSection title="Hold">
				<FormField
					v-model="holding.reason"
					type="text"
					label="Reason for the hold (required)"
					class="md:col-span-2"
					data-testid="sellos-commission-hold-reason"
				/>
			</FormSection>
			<p
				v-if="error"
				role="alert"
				data-testid="sellos-commission-error"
				class="ui-text-error"
			>
				{{ error }}
			</p>
		</FormDrawer>

		<!-- Export a partner's statement. -->
		<FormDrawer
			:open="drawer === 'export'"
			title="Export a partner's statement"
			text="A CSV of one firm's payouts. The export is logged."
			submit-label="Export the statement"
			testid="sellos-commission-export-form"
			submit-testid="sellos-commission-export"
			@close="closeForm"
			@submit="exportStatement"
		>
			<FormSection title="Statement">
				<FormField
					v-model="exporting.firm"
					type="select"
					label="Partner firm"
					:options="exportFirmOptions"
					required
					class="md:col-span-2"
					data-testid="sellos-commission-export-firm"
				/>
				<FormField
					v-model="exporting.from_date"
					type="date"
					label="From"
					data-testid="sellos-commission-export-from"
				/>
				<FormField
					v-model="exporting.to_date"
					type="date"
					label="To"
					data-testid="sellos-commission-export-to"
				/>
			</FormSection>
			<p
				v-if="error"
				role="alert"
				data-testid="sellos-commission-error"
				class="ui-text-error"
			>
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
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import SectionCard from "../components/SectionCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { commissionApi } from "../crm/commissionApi";
import { serverMessage } from "../crm/crmApi";
import { formatDate, formatMoney } from "../format";

// Commission rates and payouts (SOS-P7-04). Every change is made on the server and the lists read back. The
// server works out each payout from the rate in force on the booking date; nothing here calculates money.
const STATUSES = ["Due", "Approved", "Paid", "On hold"];
const TONES = { Due: "warning", Approved: "info", Paid: "success", "On hold": "danger" };
const rates = ref([]);
const payouts = ref([]);
const waiting = ref([]);
const totals = ref({ by_status: {} });
const options = reactive({ projects: [], firms: [], rate_types: [] });
const blank = () => ({
	project: "",
	partner_firm: "",
	rate_type: "Percentage",
	value: "",
	start_date: "",
});
const form = reactive(blank());
const exporting = reactive({ firm: "", from_date: "", to_date: "" });
const exported = ref("");
const active = ref("");
const paying = reactive({ reference: "", date: "" });
const holding = reactive({ reason: "" });
const error = ref("");
const notice = ref("");
const loadError = ref("");
const loaded = ref(false);

const search = ref("");
const statusFilter = ref("");
const statusOptions = [
	{ label: "All statuses", value: "" },
	{ label: "Due", value: "Due" },
	{ label: "Approved", value: "Approved" },
	{ label: "Paid", value: "Paid" },
	{ label: "On hold", value: "On hold" },
];
const shown = computed(() => {
	const q = search.value.trim().toLowerCase();
	return payouts.value.filter(
		(r) =>
			(!q || `${r.firm_name} ${r.target}`.toLowerCase().includes(q)) &&
			(!statusFilter.value || r.status === statusFilter.value)
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

// Which drawer is open: "rate", "pay", "hold", "export", or "" for none.
const drawer = ref("");
const activePayout = computed(() => payouts.value.find((p) => p.name === active.value) || null);

const choose = (label, list) => [
	{ label, value: "" },
	...list.map((o) => ({ label: o.label, value: o.value })),
];
const projectOptions = computed(() => choose("Choose a project", options.projects));
const firmOptions = computed(() => choose("All partners", options.firms));
const exportFirmOptions = computed(() => choose("Choose a firm", options.firms));
const rateTypes = computed(() => options.rate_types.map((t) => ({ label: t, value: t })));
const slug = (s) => s.toLowerCase().replace(/ /g, "-");

// The strip: one card per status, with what the server totals for it.
const KPI_ICONS = {
	Due: "lucide-clock",
	Approved: "lucide-badge-check",
	Paid: "lucide-wallet",
	"On hold": "lucide-circle-slash",
};
const KPI_CAPTIONS = {
	Due: "waiting for approval",
	Approved: "approved, not yet paid",
	Paid: "paid to partners",
	"On hold": "held back for now",
};
const kpis = computed(() =>
	STATUSES.map((status) => ({
		label: status,
		value: formatMoney(totals.value.by_status?.[status] || 0, 2),
		caption: KPI_CAPTIONS[status],
		icon: KPI_ICONS[status],
		tone: TONES[status],
		valueTestid: `sellos-commission-total-${slug(status)}`,
	}))
);

const payoutColumns = [
	{ key: "firm_name", label: "Firm and deal", primary: true, sortable: true, wrap: true },
	{ key: "status", label: "Status", sortable: true },
	{ key: "booking_date", label: "Booked", sortable: true },
	{
		key: "agreement_value",
		label: "Agreement value",
		sortable: true,
		align: "right",
		sortValue: (p) => Number(p.agreement_value || 0),
	},
	{
		key: "commission_total",
		label: "Commission",
		sortable: true,
		align: "right",
		sortValue: (p) => Number(p.commission_total || 0),
	},
	{
		key: "commission_due",
		label: "Due to the firm",
		sortable: true,
		align: "right",
		sortValue: (p) => Number(p.commission_due || 0),
	},
	{ key: "notes", label: "Notes", wrap: true, class: "min-w-[12rem]" },
	{ key: "actions", label: "Actions", wrap: true, class: "min-w-[12rem]" },
];
const payoutAttrs = (p) => ({
	"data-deal": p.deal,
	"data-firm": p.firm_name,
	"data-status": p.status,
});
const rateColumns = [
	{ key: "project_name", label: "Project", primary: true, sortable: true },
	{ key: "firm_name", label: "Partner firm", sortable: true },
	{ key: "value", label: "Rate", align: "right" },
	{ key: "start_date", label: "Starts", sortable: true },
	{ key: "archive", label: "Archive" },
];
const rateAttrs = (r) => ({ "data-project": r.project_name, "data-start": r.start_date });

function openForm(which) {
	error.value = "";
	exported.value = "";
	drawer.value = which;
}

function closeForm() {
	error.value = "";
	drawer.value = "";
	active.value = "";
}

function openPayout(p, which) {
	active.value = p.name;
	paying.reference = paying.date = holding.reason = "";
	error.value = "";
	notice.value = "";
	drawer.value = which;
}

function show(result) {
	rates.value = result.rates;
	payouts.value = result.payouts;
	waiting.value = result.waiting;
	totals.value = result.totals;
	for (const key of Object.keys(options)) options[key] = result[key];
}

async function load() {
	loadError.value = "";
	try {
		show(await commissionApi.overview());
	} catch (e) {
		loadError.value = serverMessage(e, "The commission could not be loaded.");
	} finally {
		loaded.value = true;
	}
}

async function run(action, done, failed) {
	error.value = "";
	notice.value = "";
	try {
		const result = await action();
		show(result);
		notice.value = done;
		active.value = "";
		if (drawer.value === "pay" || drawer.value === "hold") drawer.value = "";
		return result;
	} catch (e) {
		error.value = serverMessage(e, failed);
		return null;
	}
}

const move = (p, to) =>
	run(
		() => commissionApi.move(p.name, to),
		`${p.firm_name}: the payout is now ${to}.`,
		"The payout could not be moved."
	);

const pay = (p) =>
	run(
		() =>
			commissionApi.move(p.name, "Paid", {
				payment_reference: paying.reference,
				paid_on: paying.date,
			}),
		`${p.firm_name}: the payout is paid.`,
		"The payment could not be recorded."
	);

const hold = (p) =>
	run(
		() => commissionApi.move(p.name, "On hold", { reason: holding.reason }),
		`${p.firm_name}: the payout is on hold.`,
		"The payout could not be put on hold."
	);

const saveRate = async () => {
	if (!form.project || form.value === "" || !form.start_date) {
		error.value = "Choose the project, enter the rate and the date it starts.";
		return;
	}
	const result = await run(
		() => commissionApi.saveRate({ ...form }),
		"The rate is added. Earlier rates are kept.",
		"The rate could not be added."
	);
	if (result) {
		Object.assign(form, blank());
		drawer.value = "";
	}
};

const archive = (r) =>
	run(
		() => commissionApi.setRateArchived(r.name, 1),
		"The rate is archived. It is kept, and no longer used.",
		"The rate could not be archived."
	);

async function exportStatement() {
	error.value = "";
	exported.value = "";
	if (!exporting.firm) {
		error.value = "Choose the partner firm.";
		return;
	}
	try {
		const data = await commissionApi.exportStatement(exporting.firm, {
			from_date: exporting.from_date,
			to_date: exporting.to_date,
		});
		const link = document.createElement("a");
		link.href = URL.createObjectURL(new Blob([data.csv], { type: "text/csv" }));
		link.download = data.filename;
		link.click();
		URL.revokeObjectURL(link.href);
		drawer.value = "";
		exported.value = `${data.firm_name}: ${data.totals.count} payouts from ${
			data.from_date
		} to ${data.to_date}, ${formatMoney(data.totals.total, 2)} in all. The export is logged.`;
	} catch (e) {
		error.value = serverMessage(e, "The statement could not be exported.");
	}
}

onMounted(load);
</script>
