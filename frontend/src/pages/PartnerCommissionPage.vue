<template>
	<PageTemplate data-testid="sellos-partner-commission-page">
		<template #header>
			<PageHeader
				title="Your commission"
				text="What the company owes your firm and has paid, by deal. You see only your own firm's payouts."
				icon="lucide-badge-indian-rupee"
			/>
		</template>

		<template v-if="result" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-partner-commission-stats" />
		</template>

		<template v-if="result" #filters>
			<FilterBar
				hide-search
				:active="true"
				clear-label="Last 12 months"
				data-testid="sellos-partner-commission-filters"
				@apply="load"
				@clear="reset"
			>
				<FormField
					v-model="range.from_date"
					type="date"
					label="Booked from"
					data-testid="sellos-partner-commission-from"
				/>
				<FormField
					v-model="range.to_date"
					type="date"
					label="Booked to"
					data-testid="sellos-partner-commission-to"
				/>
				<AppButton
					type="submit"
					variant="primary"
					data-testid="sellos-partner-commission-apply"
				>
					Show statement
				</AppButton>
			</FilterBar>
		</template>

		<LoadError
			v-if="error"
			:message="error"
			data-testid="sellos-partner-commission-error"
			@retry="load"
		/>
		<LoadingSkeleton v-else-if="!result" />
		<template v-else>
			<p
				class="mb-ui-md text-sm text-ink-muted"
				data-testid="sellos-partner-commission-about"
			>
				Deals booked from {{ formatDate(result.from_date) }} to
				{{ formatDate(result.to_date) }}. All payouts in these dates:
				<b class="text-ink tabular-nums" data-testid="sellos-partner-commission-total">{{
					formatMoney(result.totals.total, 2)
				}}</b
				>.
			</p>
			<DataTable
				title="Payouts"
				caption="Payouts"
				:columns="columns"
				:rows="result.rows"
				:row-name="(row) => row.target"
				:row-attrs="rowAttrs"
				empty-title="Nothing in these dates"
				empty-text="None of your deals was booked between these dates. Choose other dates."
				empty-icon="lucide-badge-indian-rupee"
				testid="sellos-partner-commission-payouts"
				row-testid="sellos-partner-commission-payout"
				loading-testid="sellos-partner-commission-loading"
				empty-testid="sellos-partner-commission-empty"
			>
				<template #cell-status="{ row }">
					<StatusBadge :tone="TONES[row.status]" :label="row.status" />
				</template>
				<template #cell-booking_date="{ row }">
					<span class="text-ink-body">{{ formatDate(row.booking_date) }}</span>
				</template>
				<template #cell-agreement_value="{ row }">
					<span class="tabular-nums">{{ formatMoney(row.agreement_value, 2) }}</span>
				</template>
				<template #cell-partner_percent="{ row }">
					<span class="block tabular-nums">{{ row.partner_percent }}%</span>
					<span class="block text-sm text-ink-muted">{{ row.rate_basis }}</span>
				</template>
				<template #cell-commission_due="{ row }">
					<span class="tabular-nums" data-testid="sellos-partner-commission-due">{{
						formatMoney(row.commission_due, 2)
					}}</span>
				</template>
				<template #cell-notes="{ row }">
					<p v-if="row.status === 'Paid'" class="text-sm text-ink">
						Paid on {{ formatDate(row.paid_on) }}, reference
						{{ row.payment_reference }}.
					</p>
					<p v-if="row.status === 'On hold'" class="text-sm text-ink">
						On hold: {{ row.hold_reason }}
					</p>
				</template>
			</DataTable>
		</template>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import FilterBar from "../components/FilterBar.vue";
import FormField from "../components/FormField.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { commissionApi } from "../crm/commissionApi";
import { serverMessage } from "../crm/crmApi";
import { formatDate, formatMoney } from "../format";

// A partner's own commission statement (SOS-P7-04). The server reads only this firm's payouts.
const STATUSES = ["Due", "Approved", "Paid", "On hold"];
const TONES = { Due: "warning", Approved: "info", Paid: "success", "On hold": "danger" };
const KPI_ICONS = {
	Due: "lucide-clock",
	Approved: "lucide-badge-check",
	Paid: "lucide-wallet",
	"On hold": "lucide-circle-slash",
};
const KPI_CAPTIONS = {
	Due: "waiting for approval",
	Approved: "approved, not yet paid",
	Paid: "paid to your firm",
	"On hold": "held back for now",
};
const range = reactive({ from_date: "", to_date: "" });
const result = ref(null);
const error = ref("");

const slug = (s) => s.toLowerCase().replace(/ /g, "-");
const kpis = computed(() =>
	STATUSES.map((status) => ({
		label: status,
		value: formatMoney(result.value?.totals.by_status[status] || 0, 2),
		caption: KPI_CAPTIONS[status],
		icon: KPI_ICONS[status],
		tone: TONES[status],
		valueTestid: `sellos-partner-commission-total-${slug(status)}`,
	}))
);

const columns = [
	{ key: "target", label: "Deal", primary: true, sortable: true, wrap: true },
	{ key: "status", label: "Status", sortable: true },
	{ key: "booking_date", label: "Booked", sortable: true },
	{
		key: "agreement_value",
		label: "Agreement value",
		sortable: true,
		align: "right",
		sortValue: (p) => Number(p.agreement_value || 0),
	},
	{ key: "partner_percent", label: "Your share", align: "right" },
	{
		key: "commission_due",
		label: "Due to you",
		sortable: true,
		align: "right",
		sortValue: (p) => Number(p.commission_due || 0),
	},
	{ key: "notes", label: "Notes", wrap: true, class: "min-w-[12rem]" },
];
const rowAttrs = (p) => ({ "data-deal": p.deal, "data-status": p.status });

async function load() {
	error.value = "";
	try {
		result.value = await commissionApi.partnerStatement({ ...range });
		range.from_date = result.value.from_date;
		range.to_date = result.value.to_date;
	} catch (e) {
		error.value = serverMessage(e, "Your statement could not be loaded.");
	}
}

function reset() {
	range.from_date = "";
	range.to_date = "";
	load();
}

onMounted(load);
</script>
