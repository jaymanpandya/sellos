<template>
	<div data-testid="sellos-commission-page">
		<PageHeader
			title="Commission"
			text="Set the commission rate of each project, and follow what each channel partner is owed from Due to Approved to Paid."
			icon="lucide-badge-indian-rupee"
		/>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-commission-error"
			class="mb-ui-md text-sm text-accent"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-commission-notice"
			class="mb-ui-md text-sm text-ink"
		>
			{{ notice }}
		</p>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-commission-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<div class="mb-ui-md grid grid-cols-2 gap-ui-md md:grid-cols-4">
			<StatCard
				v-for="status in STATUSES"
				:key="status"
				:label="status"
				:value="rupees(totals.by_status?.[status])"
				:value-testid="`sellos-commission-total-${slug(status)}`"
			/>
		</div>

		<ListCard title="Payouts">
			<EmptyState
				v-if="loaded && !loadError && !payouts.length"
				title="No payouts yet"
				text="A payout is made when a deal with a channel partner share is approved and a rate applies."
				icon="lucide-badge-indian-rupee"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-commission-payouts">
				<li
					v-for="p in payouts"
					:key="p.name"
					data-testid="sellos-commission-payout"
					:data-name="p.name"
					:data-deal="p.deal"
					:data-firm="p.firm_name"
					:data-status="p.status"
					class="rounded-input border border-line-soft p-ui-md"
				>
					<div class="flex flex-wrap items-center gap-3">
						<span class="font-medium text-ink">{{ p.firm_name }}, {{ p.target }}</span>
						<StatusBadge
							:tone="TONES[p.status]"
							:label="p.status"
							data-testid="sellos-commission-payout-status"
						/>
						<span class="text-sm text-ink" data-testid="sellos-commission-payout-due">
							{{ rupees(p.commission_due) }}
						</span>
					</div>
					<p class="mt-1 text-sm text-ink-muted">
						Booked {{ p.booking_date }}, agreement value
						{{ rupees(p.agreement_value) }}, {{ p.rate_basis }} is
						{{ rupees(p.commission_total) }}, the firm's share is
						{{ p.partner_percent }}%.
					</p>
					<p
						v-if="p.status === 'Paid'"
						class="mt-1 text-sm text-ink"
						data-testid="sellos-commission-payout-paid"
					>
						Paid on {{ p.paid_on }}, reference {{ p.payment_reference }}.
					</p>
					<p
						v-if="p.status === 'On hold'"
						class="mt-1 text-sm text-ink"
						data-testid="sellos-commission-payout-hold"
					>
						On hold: {{ p.hold_reason }}
					</p>
					<div v-if="p.status !== 'Paid'" class="mt-ui-sm flex flex-wrap gap-2">
						<AppButton
							v-if="p.status === 'Due'"
							type="button"
							variant="primary"
							data-testid="sellos-commission-approve"
							@click="move(p, 'Approved')"
						>
							Approve
						</AppButton>
						<AppButton
							v-if="p.status === 'Approved'"
							type="button"
							variant="primary"
							data-testid="sellos-commission-pay"
							@click="open(p, 'pay')"
						>
							Record payment
						</AppButton>
						<AppButton
							v-if="p.status !== 'On hold'"
							type="button"
							data-testid="sellos-commission-hold"
							@click="open(p, 'hold')"
						>
							Put on hold
						</AppButton>
						<AppButton
							v-else
							type="button"
							data-testid="sellos-commission-release"
							@click="move(p, p.held_from || 'Due')"
						>
							Release the hold
						</AppButton>
					</div>
					<div
						v-if="active === p.name && mode === 'pay'"
						class="mt-ui-sm grid gap-ui-md md:grid-cols-2"
					>
						<FormField
							v-model="paying.reference"
							type="text"
							label="Payment reference"
							required
							data-testid="sellos-commission-reference"
						/>
						<FormField
							v-model="paying.date"
							type="date"
							label="Paid on"
							required
							data-testid="sellos-commission-paid-on"
						/>
						<AppButton
							type="button"
							variant="primary"
							data-testid="sellos-commission-pay-save"
							@click="pay(p)"
						>
							Mark as paid
						</AppButton>
					</div>
					<div v-if="active === p.name && mode === 'hold'" class="mt-ui-sm">
						<FormField
							v-model="holding.reason"
							type="text"
							label="Reason for the hold"
							required
							data-testid="sellos-commission-hold-reason"
						/>
						<AppButton
							type="button"
							variant="primary"
							class="mt-ui-sm"
							data-testid="sellos-commission-hold-save"
							@click="hold(p)"
						>
							Put on hold
						</AppButton>
					</div>
				</li>
			</ul>
		</ListCard>

		<ListCard v-if="waiting.length" title="Deals waiting for a rate" class="mt-ui-lg">
			<ul class="space-y-1 text-sm" data-testid="sellos-commission-waiting">
				<li v-for="w in waiting" :key="w.deal + w.partner_firm" class="text-ink">
					{{ w.deal }}, {{ w.firm_name }}: {{ w.reason }}
				</li>
			</ul>
		</ListCard>

		<ListCard title="Commission rates" class="mt-ui-lg">
			<EmptyState
				v-if="loaded && !loadError && !rates.length"
				title="No rates yet"
				text="Add the first rate below."
				icon="lucide-badge-indian-rupee"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-commission-rates">
				<li
					v-for="r in rates"
					:key="r.name"
					data-testid="sellos-commission-rate"
					:data-project="r.project_name"
					:data-start="r.start_date"
					class="flex flex-wrap items-center gap-3 rounded-input border border-line-soft p-ui-md text-sm text-ink"
				>
					<span class="font-medium">{{ r.project_name }}</span>
					<span>{{ r.firm_name || "All partners" }}</span>
					<span>{{
						r.rate_type === "Percentage" ? `${r.value}%` : rupees(r.value)
					}}</span>
					<span class="text-ink-muted">from {{ r.start_date }}</span>
					<AppButton
						type="button"
						data-testid="sellos-commission-rate-archive"
						@click="archive(r)"
					>
						Archive
					</AppButton>
				</li>
			</ul>
		</ListCard>

		<ListCard title="Add a rate" class="mt-ui-lg">
			<div class="grid gap-ui-md md:grid-cols-2">
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
			</div>
			<AppButton
				type="button"
				variant="primary"
				class="mt-ui-md"
				data-testid="sellos-commission-save-rate"
				@click="saveRate"
			>
				Add the rate
			</AppButton>
		</ListCard>

		<ListCard title="Export a partner's statement" class="mt-ui-lg">
			<div class="grid gap-ui-md md:grid-cols-3">
				<FormField
					v-model="exporting.firm"
					type="select"
					label="Partner firm"
					:options="exportFirmOptions"
					required
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
			</div>
			<AppButton
				type="button"
				variant="primary"
				class="mt-ui-md"
				data-testid="sellos-commission-export"
				@click="exportStatement"
			>
				Export the statement
			</AppButton>
			<p
				v-if="exported"
				class="mt-ui-sm text-sm text-ink"
				data-testid="sellos-commission-exported"
			>
				{{ exported }}
			</p>
		</ListCard>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import StatCard from "../components/StatCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { commissionApi } from "../crm/commissionApi";
import { serverMessage } from "../crm/crmApi";

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
const mode = ref("");
const paying = reactive({ reference: "", date: "" });
const holding = reactive({ reason: "" });
const error = ref("");
const notice = ref("");
const loadError = ref("");
const loaded = ref(false);

const choose = (label, list) => [
	{ label, value: "" },
	...list.map((o) => ({ label: o.label, value: o.value })),
];
const projectOptions = computed(() => choose("Choose a project", options.projects));
const firmOptions = computed(() => choose("All partners", options.firms));
const exportFirmOptions = computed(() => choose("Choose a firm", options.firms));
const rateTypes = computed(() => options.rate_types.map((t) => ({ label: t, value: t })));
const rupees = (n) =>
	`Rs ${new Intl.NumberFormat("en-IN", {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	}).format(Number(n || 0))}`;
const slug = (s) => s.toLowerCase().replace(/ /g, "-");

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
		return result;
	} catch (e) {
		error.value = serverMessage(e, failed);
		return null;
	}
}

function open(p, which) {
	active.value = p.name;
	mode.value = which;
	paying.reference = paying.date = holding.reason = "";
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
	if (result) Object.assign(form, blank());
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
		exported.value = `${data.firm_name}: ${data.totals.count} payouts from ${
			data.from_date
		} to ${data.to_date}, ${rupees(data.totals.total)} in all. The export is logged.`;
	} catch (e) {
		error.value = serverMessage(e, "The statement could not be exported.");
	}
}

onMounted(load);
</script>
