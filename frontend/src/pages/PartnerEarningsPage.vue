<template>
	<PageTemplate data-testid="sellos-partner-earnings-page">
		<template #header>
			<PageHeader
				title="Your deals and earnings"
				text="Your own deals, what you have earned, what you may still earn, and your QR code to share."
				icon="lucide-badge-indian-rupee"
			/>
		</template>

		<template v-if="result && result.firm" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-partner-earnings-stats" />
		</template>

		<LoadError
			v-if="error"
			:message="error"
			data-testid="sellos-partner-earnings-error"
			@retry="load"
		/>
		<LoadingSkeleton v-else-if="!result" />
		<EmptyState
			v-else-if="!result.firm"
			title="Nothing to show yet"
			text="Your deals and earnings appear here once the company has approved your firm."
			icon="lucide-badge-indian-rupee"
		/>
		<template v-else>
			<DataTable
				title="Your deals"
				caption="Your deals"
				:columns="columns"
				:rows="result.deals"
				:row-name="(row) => row.target"
				:row-attrs="rowAttrs"
				empty-title="No deals yet"
				empty-text="A deal appears here once the company records one with a share for your firm."
				empty-icon="lucide-badge-indian-rupee"
				testid="sellos-partner-earnings-deals"
				row-testid="sellos-partner-earnings-deal"
				loading-testid="sellos-partner-earnings-loading"
				empty-testid="sellos-partner-earnings-empty"
			>
				<template #cell-approval_status="{ row }">
					<span class="flex flex-wrap items-center gap-ui-sm">
						<StatusBadge
							:tone="row.approval_status === 'Approved' ? 'success' : 'warning'"
							:label="row.approval_status"
						/>
						<StatusBadge
							v-if="row.payout_status"
							:tone="TONES[row.payout_status] || 'neutral'"
							:label="`Commission ${row.payout_status}`"
						/>
					</span>
				</template>
				<template #cell-deal_date="{ row }">
					<span class="text-ink-body">{{ formatDate(row.deal_date) }}</span>
				</template>
				<template #cell-percent="{ row }">
					<span class="tabular-nums">{{ row.percent }}%</span>
				</template>
				<template #cell-commission_due="{ row }">
					<span
						v-if="row.commission_due !== null"
						class="tabular-nums"
						data-testid="sellos-partner-earnings-deal-amount"
						>{{ formatMoney(row.commission_due, 2) }}</span
					>
				</template>
			</DataTable>

			<ListCard title="Your QR code" class="mt-ui-md">
				<div class="flex flex-wrap items-center gap-ui-md">
					<img
						:src="result.qr"
						alt="Your QR code"
						width="160"
						height="160"
						data-testid="sellos-partner-earnings-qr"
					/>
					<div class="text-sm text-ink">
						<p>Share this code or your link with buyers and with your own team.</p>
						<p
							class="mt-ui-sm break-all text-ink-muted"
							data-testid="sellos-partner-earnings-link"
						>
							{{ result.link }}
						</p>
						<p class="mt-ui-sm text-ink-muted">Partner code {{ result.firm.name }}</p>
					</div>
				</div>
			</ListCard>
		</template>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import DataTable from "../components/DataTable.vue";
import EmptyState from "../components/EmptyState.vue";
import KpiStrip from "../components/KpiStrip.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { partnerViewsApi } from "../crm/partnerViewsApi";
import { formatDate, formatMoney } from "../format";

// SOS-P5-06: a partner's own deals, earnings and QR code. The server reads only this firm's records.
const TONES = { Due: "warning", Approved: "info", Paid: "success", "On hold": "danger" };
const result = ref(null);
const error = ref("");

const kpis = computed(() => [
	{
		label: "Earned so far",
		value: formatMoney(result.value?.earned || 0, 2),
		caption: "Commission already paid to you",
		icon: "lucide-wallet",
		tone: "success",
		valueTestid: "sellos-partner-earnings-earned",
	},
	{
		label: "Potential earnings",
		value: formatMoney(result.value?.potential || 0, 2),
		caption: "Commission due, approved or on hold",
		icon: "lucide-hourglass",
		tone: "warning",
		valueTestid: "sellos-partner-earnings-potential",
	},
]);

const columns = [
	{ key: "target", label: "Deal", primary: true, sortable: true, wrap: true },
	{ key: "approval_status", label: "Status", sortable: true },
	{ key: "deal_date", label: "Booked", sortable: true },
	{
		key: "percent",
		label: "Your share",
		sortable: true,
		align: "right",
		sortValue: (d) => Number(d.percent || 0),
	},
	{
		key: "commission_due",
		label: "Commission",
		sortable: true,
		align: "right",
		sortValue: (d) => (d.commission_due === null ? null : Number(d.commission_due)),
	},
];
const rowAttrs = (d) => ({
	"data-deal": d.name,
	"data-status": d.payout_status || d.approval_status,
});

async function load() {
	error.value = "";
	try {
		result.value = await partnerViewsApi.overview();
	} catch (e) {
		error.value = serverMessage(e, "Your deals and earnings could not be loaded.");
	}
}

onMounted(load);
</script>
