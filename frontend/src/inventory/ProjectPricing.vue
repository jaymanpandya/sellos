<template>
	<section data-testid="sellos-pricing">
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-pricing-error"
			class="mb-ui-md text-sm text-accent"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-pricing-notice"
			class="mb-ui-md text-sm text-ink"
		>
			{{ notice }}
		</p>

		<ListCard title="Price lists">
			<EmptyState
				v-if="state && !state.price_lists.length"
				title="No price list yet"
				text="A Company Admin adds a dated price list. The one in force is used for cost sheets."
				icon="lucide-indian-rupee"
			/>
			<ul v-if="state" class="space-y-ui-sm" data-testid="sellos-pricing-lists">
				<li
					v-for="l in state.price_lists"
					:key="l.name"
					data-testid="sellos-pricelist-row"
					:data-title="l.title"
					:data-in-force="l.in_force ? 1 : 0"
					class="rounded-input border border-line-soft p-ui-md"
				>
					<div class="flex flex-wrap items-center gap-3">
						<span class="font-medium text-ink">{{ l.title }}</span>
						<StatusBadge
							:tone="l.in_force ? 'success' : l.scheduled ? 'info' : 'neutral'"
							:label="
								l.in_force ? 'In force' : l.scheduled ? 'Scheduled' : 'Earlier'
							"
							data-testid="sellos-pricelist-state"
						/>
						<span class="text-sm text-ink-muted">From {{ l.effective_from }}</span>
					</div>
					<p class="text-sm text-ink-muted">
						{{ rupees(l.base_rate) }} per sq ft of carpet area<span
							v-if="Number(l.floor_rise_rate)"
						>
							, floor rise {{ rupees(l.floor_rise_rate) }} per sq ft for each floor
							above floor {{ l.floor_rise_from_floor }}</span
						>.
					</p>
					<p v-if="l.charges.length" class="text-sm text-ink-muted">
						<span v-for="(c, i) in l.charges" :key="i">
							{{ c.charge_name }} ({{ c.charge_type.toLowerCase() }}):
							{{ rupees(c.value)
							}}{{ c.basis === "Rate per sq ft" ? " per sq ft" : "" }}
							<span v-if="c.always_apply">, always added</span
							><span v-if="i < l.charges.length - 1">; </span>
						</span>
					</p>
				</li>
			</ul>
		</ListCard>

		<form
			v-if="state && state.can_edit"
			class="ui-card mt-ui-md"
			data-testid="sellos-pricelist-form"
			@submit.prevent="savePriceList"
		>
			<h2 class="ui-card-heading mb-ui-md">New price list</h2>
			<div class="grid grid-cols-1 gap-x-ui-md gap-y-ui-md md:grid-cols-2">
				<FormField
					v-model="list.title"
					label="Title"
					required
					data-testid="sellos-pricelist-title"
				/>
				<FormField
					v-model="list.effective_from"
					type="date"
					label="In force from"
					required
					data-testid="sellos-pricelist-from"
				/>
				<FormField
					v-model="list.base_rate"
					type="number"
					label="Base rate per sq ft of carpet area (Rs)"
					required
					data-testid="sellos-pricelist-base"
				/>
				<FormField
					v-model="list.floor_rise_rate"
					type="number"
					label="Floor rise per sq ft per floor (Rs)"
					data-testid="sellos-pricelist-rise"
				/>
				<FormField
					v-model="list.floor_rise_from_floor"
					type="number"
					label="Floor rise applies above floor"
					data-testid="sellos-pricelist-rise-floor"
				/>
			</div>
			<h3 class="mt-ui-md text-sm font-medium text-ink">
				Charges (preferred location, parking and other)
			</h3>
			<div
				v-for="(c, i) in list.charges"
				:key="i"
				class="mt-ui-sm grid grid-cols-1 items-end gap-ui-sm md:grid-cols-6"
				data-testid="sellos-charge-row"
			>
				<FormField
					v-model="c.charge_type"
					type="select"
					label="Kind"
					:options="state.charge_types"
					:data-testid="`sellos-charge-kind-${i}`"
				/>
				<FormField
					v-model="c.charge_name"
					label="Name"
					:data-testid="`sellos-charge-name-${i}`"
				/>
				<FormField
					v-model="c.basis"
					type="select"
					label="Basis"
					:options="state.bases"
					:data-testid="`sellos-charge-basis-${i}`"
				/>
				<FormField
					v-model="c.value"
					type="number"
					label="Amount or rate (Rs)"
					:data-testid="`sellos-charge-value-${i}`"
				/>
				<AppCheckbox
					:model-value="!!c.always_apply || c.charge_type === 'Parking'"
					label="Always added"
					:disabled="c.charge_type === 'Parking'"
					:data-testid="`sellos-charge-always-${i}`"
					@update:model-value="c.always_apply = $event ? 1 : 0"
				/>
				<AppButton
					type="button"
					:data-testid="`sellos-charge-remove-${i}`"
					@click="list.charges.splice(i, 1)"
				>
					Remove charge
				</AppButton>
			</div>
			<div class="mt-ui-md flex flex-wrap gap-ui-sm">
				<AppButton
					type="button"
					data-testid="sellos-pricelist-add-charge"
					@click="addCharge"
				>
					Add a charge
				</AppButton>
				<AppButton type="submit" variant="primary" data-testid="sellos-pricelist-save">
					Save price list
				</AppButton>
			</div>
			<p class="mt-ui-sm text-xs text-ink-muted">
				A price list is never changed once saved. Make a new one with a later date. Parking
				is per parking slot of the unit and always added.
			</p>
		</form>

		<ListCard title="Payment plans" class="mt-ui-md">
			<EmptyState
				v-if="state && !state.payment_plans.length"
				title="No payment plan yet"
				text="A Company Admin adds payment plan templates. Their percentages add up to 100."
				icon="lucide-calendar-clock"
			/>
			<ul v-if="state" class="space-y-ui-sm" data-testid="sellos-pricing-plans">
				<li
					v-for="p in state.payment_plans"
					:key="p.name"
					data-testid="sellos-plan-row"
					:data-name="p.plan_name"
					:data-archived="p.archived"
					class="rounded-input border border-line-soft p-ui-md"
				>
					<div class="flex flex-wrap items-center gap-3">
						<span class="font-medium text-ink">{{ p.plan_name }}</span>
						<StatusBadge
							:tone="p.archived ? 'neutral' : 'info'"
							:label="p.archived ? 'Archived' : p.plan_type"
						/>
						<AppButton
							v-if="state.can_edit"
							type="button"
							data-testid="sellos-plan-archive"
							@click="archivePlan(p)"
						>
							{{ p.archived ? "Restore" : "Archive" }}
						</AppButton>
					</div>
					<p class="text-sm text-ink-muted">
						<span v-for="(r, i) in p.instalments" :key="i">
							{{ r.label }} {{ r.percent }}%<span v-if="r.due_on">
								({{ r.due_on }})</span
							><span v-else-if="p.plan_type === 'Time linked'">
								(after {{ r.days_after_booking }} days)</span
							><span v-if="i < p.instalments.length - 1">, </span>
						</span>
					</p>
				</li>
			</ul>
		</ListCard>

		<form
			v-if="state && state.can_edit"
			class="ui-card mt-ui-md"
			data-testid="sellos-plan-form"
			@submit.prevent="savePlan"
		>
			<h2 class="ui-card-heading mb-ui-md">New payment plan</h2>
			<div class="grid grid-cols-1 gap-x-ui-md gap-y-ui-md md:grid-cols-2">
				<FormField
					v-model="plan.plan_name"
					label="Plan name"
					required
					data-testid="sellos-plan-name"
				/>
				<FormField
					v-model="plan.plan_type"
					type="select"
					label="Kind"
					:options="state.plan_types"
					required
					data-testid="sellos-plan-type"
				/>
			</div>
			<div
				v-for="(r, i) in plan.instalments"
				:key="i"
				class="mt-ui-sm grid grid-cols-1 items-end gap-ui-sm md:grid-cols-5"
				data-testid="sellos-instalment-row"
			>
				<FormField
					v-model="r.label"
					label="Instalment"
					:data-testid="`sellos-instalment-label-${i}`"
				/>
				<FormField
					v-if="plan.plan_type === 'Time linked'"
					v-model="r.days_after_booking"
					type="number"
					label="Days after booking"
					:data-testid="`sellos-instalment-days-${i}`"
				/>
				<FormField
					v-else
					v-model="r.due_on"
					label="Due on"
					:data-testid="`sellos-instalment-due-${i}`"
				/>
				<FormField
					v-model="r.percent"
					type="number"
					label="Percent of the total"
					:data-testid="`sellos-instalment-percent-${i}`"
				/>
				<AppButton
					type="button"
					:data-testid="`sellos-instalment-remove-${i}`"
					@click="plan.instalments.splice(i, 1)"
				>
					Remove instalment
				</AppButton>
			</div>
			<p
				class="mt-ui-sm text-sm"
				:class="planTotal === 100 ? 'text-ink' : 'text-accent'"
				data-testid="sellos-plan-total"
			>
				Total: {{ planTotal }} percent<span v-if="planTotal !== 100">
					(it must add up to 100)</span
				>
			</p>
			<div class="mt-ui-md flex flex-wrap gap-ui-sm">
				<AppButton
					type="button"
					data-testid="sellos-plan-add-instalment"
					@click="addInstalment"
				>
					Add an instalment
				</AppButton>
				<AppButton type="submit" variant="primary" data-testid="sellos-plan-save">
					Save payment plan
				</AppButton>
			</div>
		</form>

		<div class="ui-card mt-ui-md" data-testid="sellos-rates">
			<h2 class="ui-card-heading mb-ui-md">Cost sheet percentages</h2>
			<p v-if="state && !state.rates" class="mb-ui-sm text-sm text-accent">
				Not set yet. Cost sheets wait until a Company Admin sets them.
			</p>
			<p
				v-else-if="state && !state.can_edit"
				class="text-sm text-ink-muted"
				data-testid="sellos-rates-text"
			>
				Stamp duty {{ state.rates.stamp_duty_percent }}%, registration
				{{ state.rates.registration_percent }}%, GST {{ state.rates.gst_percent }}%.
			</p>
			<div v-if="state && state.can_edit" class="flex flex-wrap items-end gap-ui-sm">
				<FormField
					v-model="rates.stamp"
					type="number"
					label="Stamp duty (%)"
					class="w-40"
					data-testid="sellos-rate-stamp"
				/>
				<FormField
					v-model="rates.registration"
					type="number"
					label="Registration (%)"
					class="w-40"
					data-testid="sellos-rate-registration"
				/>
				<FormField
					v-model="rates.gst"
					type="number"
					label="GST (%)"
					class="w-40"
					data-testid="sellos-rate-gst"
				/>
				<AppButton type="button" data-testid="sellos-rates-save" @click="saveRates">
					Save percentages
				</AppButton>
			</div>
		</div>
	</section>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";

import AppButton from "../components/AppButton.vue";
import AppCheckbox from "../components/AppCheckbox.vue";
import EmptyState from "../components/EmptyState.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { pricingApi, rupees } from "./inventoryApi";

// A project's dated price lists, payment plan templates and the company's cost sheet percentages
// (SOS-P7-07). A Company Admin makes and archives them; others read. Every change is made on the server,
// which answers with the state again.
const props = defineProps({
	project: { type: String, required: true },
});

const state = ref(null);
const error = ref("");
const notice = ref("");
const blankList = () => ({
	title: "",
	effective_from: "",
	base_rate: "",
	floor_rise_rate: "",
	floor_rise_from_floor: "",
	charges: [],
});
const blankPlan = () => ({
	plan_name: "",
	plan_type: "Construction linked",
	instalments: [{ label: "", due_on: "", days_after_booking: "", percent: "" }],
});
const list = reactive(blankList());
const plan = reactive(blankPlan());
const rates = reactive({ stamp: "", registration: "", gst: "" });

const planTotal = computed(
	() =>
		Math.round(plan.instalments.reduce((sum, r) => sum + Number(r.percent || 0), 0) * 100) /
		100
);

function show(data) {
	state.value = data;
	if (data.rates) {
		rates.stamp = data.rates.stamp_duty_percent;
		rates.registration = data.rates.registration_percent;
		rates.gst = data.rates.gst_percent;
	}
}

async function act(action, message) {
	error.value = "";
	notice.value = "";
	try {
		show(await action());
		notice.value = message;
		return true;
	} catch (e) {
		error.value = serverMessage(e, "The change could not be saved.");
		return false;
	}
}

async function load() {
	try {
		show(await pricingApi.project(props.project));
	} catch (e) {
		error.value = serverMessage(e, "The price lists could not be loaded.");
	}
}
watch(() => props.project, load, { immediate: true });

const addCharge = () =>
	list.charges.push({
		charge_type: "Other",
		charge_name: "",
		basis: "Amount",
		value: "",
		always_apply: 0,
	});
const addInstalment = () =>
	plan.instalments.push({ label: "", due_on: "", days_after_booking: "", percent: "" });

async function savePriceList() {
	const values = {
		title: list.title,
		effective_from: list.effective_from,
		base_rate: list.base_rate === "" ? null : Number(list.base_rate),
		floor_rise_rate: Number(list.floor_rise_rate || 0),
		floor_rise_from_floor: Number(list.floor_rise_from_floor || 0),
		charges: list.charges.map((c) => ({ ...c, value: Number(c.value || 0) })),
	};
	if (
		await act(
			() => pricingApi.savePriceList(props.project, values),
			`The price list ${list.title} is saved.`
		)
	) {
		Object.assign(list, blankList());
	}
}

async function savePlan() {
	const values = {
		plan_name: plan.plan_name,
		plan_type: plan.plan_type,
		instalments: plan.instalments.map((r) => ({
			label: r.label,
			due_on: plan.plan_type === "Time linked" ? "" : r.due_on,
			days_after_booking:
				plan.plan_type === "Time linked" ? Number(r.days_after_booking || 0) : 0,
			percent: Number(r.percent || 0),
		})),
	};
	if (
		await act(
			() => pricingApi.savePlan(props.project, values),
			`The payment plan ${plan.plan_name} is saved.`
		)
	) {
		Object.assign(plan, blankPlan());
	}
}

const archivePlan = (p) =>
	act(
		() => pricingApi.archivePlan(p.name, p.archived ? 0 : 1),
		p.archived ? `${p.plan_name} is restored.` : `${p.plan_name} is archived.`
	);

const saveRates = () =>
	act(async () => {
		await pricingApi.saveRates(rates.stamp, rates.registration, rates.gst);
		return pricingApi.project(props.project);
	}, "The percentages are saved.");
</script>
