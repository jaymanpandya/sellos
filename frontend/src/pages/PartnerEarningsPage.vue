<template>
	<div data-testid="sellos-partner-earnings-page">
		<PageHeader
			title="Your deals and earnings"
			text="Your own deals, what you have earned so far, what you may still earn, and your QR code to share."
			icon="lucide-badge-indian-rupee"
		/>
		<div v-if="error" data-testid="sellos-partner-earnings-error">
			<LoadError :message="error" @retry="load" />
		</div>
		<LoadingSkeleton v-else-if="!result" />
		<EmptyState
			v-else-if="!result.firm"
			title="Nothing to show yet"
			text="Your deals and earnings appear here once the company has approved your firm."
			icon="lucide-badge-indian-rupee"
		/>
		<template v-else>
			<div class="mb-ui-md grid grid-cols-2 gap-ui-md">
				<StatCard
					label="Earned so far"
					:value="rupees(result.earned)"
					note="Commission already paid to you"
					value-testid="sellos-partner-earnings-earned"
				/>
				<StatCard
					label="Potential earnings"
					:value="rupees(result.potential)"
					note="Commission due, approved or on hold"
					value-testid="sellos-partner-earnings-potential"
				/>
			</div>

			<ListCard title="Your QR code" class="mb-ui-md">
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

			<ListCard title="Your deals">
				<EmptyState
					v-if="!result.deals.length"
					title="No deals yet"
					text="A deal appears here once the company records one with a share for your firm."
					icon="lucide-badge-indian-rupee"
				/>
				<ul v-else class="space-y-ui-sm" data-testid="sellos-partner-earnings-deals">
					<li
						v-for="d in result.deals"
						:key="d.name"
						data-testid="sellos-partner-earnings-deal"
						:data-deal="d.name"
						:data-status="d.payout_status || d.approval_status"
						class="rounded-input border border-line-soft p-ui-md"
					>
						<div class="flex flex-wrap items-center gap-3">
							<span class="font-medium text-ink">{{ d.target }}</span>
							<StatusBadge
								:tone="d.approval_status === 'Approved' ? 'success' : 'warning'"
								:label="d.approval_status"
							/>
							<StatusBadge
								v-if="d.payout_status"
								:tone="TONES[d.payout_status] || 'neutral'"
								:label="`Commission ${d.payout_status}`"
							/>
						</div>
						<p class="mt-1 text-sm text-ink-muted">
							Booked {{ d.deal_date }}, your share {{ d.percent }}%<span
								v-if="d.commission_due !== null"
								data-testid="sellos-partner-earnings-deal-amount"
							>
								, {{ rupees(d.commission_due) }}</span
							>.
						</p>
					</li>
				</ul>
			</ListCard>
		</template>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue";

import EmptyState from "../components/EmptyState.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import StatCard from "../components/StatCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { partnerViewsApi } from "../crm/partnerViewsApi";

// SOS-P5-06: a partner's own deals, earnings and QR code. The server reads only this firm's records.
const TONES = { Due: "warning", Approved: "info", Paid: "success", "On hold": "danger" };
const result = ref(null);
const error = ref("");

const rupees = (n) =>
	`Rs ${new Intl.NumberFormat("en-IN", {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	}).format(Number(n || 0))}`;

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
