<template>
	<div data-testid="sellos-partner-commission-page">
		<PageHeader
			title="Your commission"
			text="What the company owes your firm and has paid, by deal. You see only your own firm's payouts."
			icon="lucide-badge-indian-rupee"
		/>
		<div v-if="error" data-testid="sellos-partner-commission-error">
			<LoadError :message="error" @retry="load" />
		</div>
		<LoadingSkeleton v-else-if="!result" />
		<template v-else>
			<FilterBar
				apply-label="Show statement"
				clear-label="Last 12 months"
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
			</FilterBar>
			<p
				class="mb-ui-md text-sm text-ink-muted"
				data-testid="sellos-partner-commission-about"
			>
				Deals booked from {{ result.from_date }} to {{ result.to_date }}.
			</p>
			<div class="mb-ui-md grid grid-cols-2 gap-ui-md md:grid-cols-5">
				<StatCard
					v-for="status in STATUSES"
					:key="status"
					:label="status"
					:value="rupees(result.totals.by_status[status])"
					:value-testid="`sellos-partner-commission-total-${slug(status)}`"
				/>
				<StatCard
					label="All payouts"
					:value="rupees(result.totals.total)"
					value-testid="sellos-partner-commission-total"
				/>
			</div>
			<ListCard title="Payouts">
				<EmptyState
					v-if="!result.rows.length"
					title="Nothing in these dates"
					text="None of your deals was booked between these dates. Choose other dates."
					icon="lucide-badge-indian-rupee"
				/>
				<ul v-else class="space-y-ui-sm" data-testid="sellos-partner-commission-payouts">
					<li
						v-for="p in result.rows"
						:key="p.name"
						data-testid="sellos-partner-commission-payout"
						:data-deal="p.deal"
						:data-status="p.status"
						class="rounded-input border border-line-soft p-ui-md"
					>
						<div class="flex flex-wrap items-center gap-3">
							<span class="font-medium text-ink">{{ p.target }}</span>
							<StatusBadge :tone="TONES[p.status]" :label="p.status" />
							<span
								class="text-sm text-ink"
								data-testid="sellos-partner-commission-due"
							>
								{{ rupees(p.commission_due) }}
							</span>
						</div>
						<p class="mt-1 text-sm text-ink-muted">
							Booked {{ p.booking_date }}, agreement value
							{{ rupees(p.agreement_value) }}, {{ p.rate_basis }}, your share
							{{ p.partner_percent }}%.
						</p>
						<p v-if="p.status === 'Paid'" class="mt-1 text-sm text-ink">
							Paid on {{ p.paid_on }}, reference {{ p.payment_reference }}.
						</p>
						<p v-if="p.status === 'On hold'" class="mt-1 text-sm text-ink">
							On hold: {{ p.hold_reason }}
						</p>
					</li>
				</ul>
			</ListCard>
		</template>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import EmptyState from "../components/EmptyState.vue";
import FilterBar from "../components/FilterBar.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import StatCard from "../components/StatCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { commissionApi } from "../crm/commissionApi";
import { serverMessage } from "../crm/crmApi";

// A partner's own commission statement (SOS-P7-04). The server reads only this firm's payouts.
const STATUSES = ["Due", "Approved", "Paid", "On hold"];
const TONES = { Due: "warning", Approved: "info", Paid: "success", "On hold": "danger" };
const range = reactive({ from_date: "", to_date: "" });
const result = ref(null);
const error = ref("");

const rupees = (n) =>
	`Rs ${new Intl.NumberFormat("en-IN", {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	}).format(Number(n || 0))}`;
const slug = (s) => s.toLowerCase().replace(/ /g, "-");

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
