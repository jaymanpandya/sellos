<template>
	<div data-testid="sellos-deals-page">
		<PageHeader
			title="Deals"
			text="A deal links a client to a unit or a property at a price. The commission is split among the agent, the channel partner and the company, the shares add up to 100 percent, and a Company Admin approves the split."
			icon="lucide-handshake"
		/>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-deal-error"
			class="mb-ui-md text-sm text-accent"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-deal-notice"
			class="mb-ui-md text-sm text-ink"
		>
			{{ notice }}
		</p>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-deal-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<ListCard title="Deals">
			<EmptyState
				v-if="loaded && !loadError && !deals.length"
				title="No deals yet"
				text="Record the first deal below."
				icon="lucide-handshake"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-deal-list">
				<li
					v-for="d in deals"
					:key="d.name"
					data-testid="sellos-deal-row"
					:data-name="d.name"
					:data-client="d.client_name"
					:data-status="d.approval_status"
					class="rounded-input border border-line-soft p-ui-md"
				>
					<div class="flex flex-wrap items-center gap-3">
						<span class="font-medium text-ink" data-testid="sellos-deal-title">
							{{ d.client_name }}, {{ d.target }}
						</span>
						<StatusBadge
							:tone="d.approval_status === 'Approved' ? 'success' : 'warning'"
							:label="d.approval_status"
							data-testid="sellos-deal-status"
						/>
						<span class="text-sm text-ink-muted" data-testid="sellos-deal-money">
							Price {{ rupees(d.price) }}, commission
							{{ rupees(d.commission_amount) }}
						</span>
					</div>
					<ul class="mt-ui-sm space-y-1" data-testid="sellos-deal-splits">
						<li
							v-for="(s, n) in d.splits"
							:key="n"
							data-testid="sellos-deal-split"
							:data-party="s.party_type"
							class="text-sm text-ink"
						>
							{{ s.party_type }}: {{ s.party }}, {{ s.percent }}% ({{
								rupees(s.amount)
							}})
						</li>
					</ul>
					<p
						v-if="d.approval_status === 'Approved'"
						class="mt-ui-sm text-sm text-ink-muted"
						data-testid="sellos-deal-approved"
					>
						Approved by {{ d.approved_by_name }} on {{ d.approved_on }}. The split is
						kept unless it is reopened.
					</p>
					<div class="mt-ui-sm">
						<AppButton
							v-if="d.approval_status !== 'Approved'"
							type="button"
							variant="primary"
							data-testid="sellos-deal-approve"
							@click="approve(d)"
						>
							Approve the split
						</AppButton>
						<AppButton
							v-else
							type="button"
							data-testid="sellos-deal-reopen"
							@click="reopen(d)"
						>
							Reopen the split
						</AppButton>
					</div>
				</li>
			</ul>
		</ListCard>

		<ListCard title="Record a deal" class="mt-ui-lg">
			<div class="grid gap-ui-md md:grid-cols-2">
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
			</div>

			<h3 class="mt-ui-md font-medium text-ink">Commission split</h3>
			<p class="text-sm text-ink-muted">
				Leave a share empty to leave that party out. The shares must add up to 100.
			</p>
			<div class="mt-ui-sm grid gap-ui-md md:grid-cols-2">
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
			</div>
			<p
				class="mt-ui-sm text-sm"
				:class="total === 100 ? 'text-ink' : 'text-accent'"
				data-testid="sellos-deal-total"
			>
				The split adds up to {{ total }} percent.
			</p>
			<div class="mt-ui-md">
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-deal-save"
					@click="save"
				>
					Record deal
				</AppButton>
			</div>
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
import MoneyField from "../components/MoneyField.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { dealApi } from "../crm/dealsApi";

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

const choose = (label, list) => [
	{ label, value: "" },
	...list.map((o) => ({ label: o.label, value: o.value })),
];
const clientOptions = computed(() => choose("Choose a client", options.clients));
const unitOptions = computed(() => choose("No unit", options.units));
const propertyOptions = computed(() => choose("No property", options.properties));
const agentOptions = computed(() => choose("No agent", options.agents));
const firmOptions = computed(() => choose("No channel partner", options.firms));

const rupees = (n) => `Rs ${new Intl.NumberFormat("en-IN").format(Number(n || 0))}`;
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
