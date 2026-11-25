<template>
	<SectionCard title="Book a unit" data-testid="sellos-lead-booking">
		<p
			v-if="panel && panel.consent.warning"
			data-testid="sellos-booking-consent"
			:data-status="panel.consent.status"
			class="mb-ui-sm ui-text-muted"
		>
			{{ panel.consent.message }} This does not stop the booking.
		</p>
		<p v-if="error" role="alert" data-testid="sellos-booking-error" class="ui-text-error">
			{{ error }}
		</p>

		<ul v-if="panel && panel.active.length" class="ui-list">
			<li
				v-for="deal in panel.active"
				:key="deal.name"
				class="space-y-ui-sm"
				data-testid="sellos-booking-row"
				:data-deal="deal.name"
				:data-unit="deal.unit_label"
			>
				<div class="flex flex-wrap items-center gap-3">
					<span class="ui-text-strong">{{ deal.unit_label }}</span>
					<StatusBadge tone="success" label="Booked" />
					<span class="ui-text-muted">
						{{ rupees(deal.price) }}, booking amount {{ rupees(deal.booking_amount) }}
					</span>
					<AppButton
						type="button"
						data-testid="sellos-booking-cancel-open"
						@click="cancelling = cancelling === deal.name ? '' : deal.name"
					>
						Cancel booking
					</AppButton>
				</div>
				<form
					v-if="cancelling === deal.name"
					class="mt-ui-sm flex flex-wrap items-end gap-ui-sm"
					@submit.prevent="cancel(deal.name)"
				>
					<FormField
						v-model="reason"
						label="Reason for cancelling"
						class="w-96"
						data-testid="sellos-booking-cancel-reason"
					/>
					<AppButton type="submit" data-testid="sellos-booking-cancel-confirm">
						Confirm cancellation
					</AppButton>
				</form>
			</li>
		</ul>

		<form
			v-if="panel && panel.can_book"
			class="mt-ui-sm space-y-ui-md"
			data-testid="sellos-booking-form"
			@submit.prevent="book"
		>
			<p v-if="panel.partner" class="ui-text-muted" data-testid="sellos-booking-partner">
				{{ panel.partner }} registered this buyer and shares the commission.
			</p>
			<div class="grid grid-cols-1 gap-ui-md sm:grid-cols-2">
				<FormField
					v-model="unit"
					type="select"
					label="Unit"
					:options="unitOptions"
					required
					data-testid="sellos-booking-unit"
				/>
				<FormField
					v-if="sheetOptions.length"
					v-model="sheet"
					type="select"
					label="Cost sheet"
					:options="sheetOptions"
					data-testid="sellos-booking-sheet"
				/>
				<MoneyField
					v-model="price"
					label="Agreed price (₹)"
					data-testid="sellos-booking-price"
				/>
				<MoneyField
					v-model="amount"
					label="Booking amount (₹)"
					data-testid="sellos-booking-amount"
				/>
			</div>
			<AppButton type="submit" data-testid="sellos-booking-confirm"
				>Confirm booking</AppButton
			>
		</form>

		<ul v-if="panel && panel.cancelled.length" class="mt-ui-md ui-list">
			<li
				v-for="deal in panel.cancelled"
				:key="deal.name"
				class="ui-text-muted"
				data-testid="sellos-booking-cancelled"
				:data-deal="deal.name"
			>
				{{ deal.unit_label }}: cancelled by {{ deal.cancelled_by_name }}, "{{
					deal.cancellation_reason
				}}"
			</li>
		</ul>
	</SectionCard>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";

import AppButton from "../components/AppButton.vue";
import FormField from "../components/FormField.vue";
import SectionCard from "../components/SectionCard.vue";
import MoneyField from "../components/MoneyField.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { bookingApi, rupees } from "./inventoryApi";

// Book a unit for the lead: confirming makes the deal, marks the unit Booked and moves the lead to Booking
// in one step. Cancelling needs a reason and leaves the lead's stage for the agent (SOS-P7-10).
const props = defineProps({ lead: { type: String, required: true } });
const emit = defineEmits(["changed"]);

const panel = ref(null);
const error = ref("");
const unit = ref("");
const sheet = ref("");
const price = ref("");
const amount = ref("");
const cancelling = ref("");
const reason = ref("");

const unitOptions = computed(() =>
	(panel.value?.units || []).map((u) => ({
		value: u.name,
		label: `${u.label} (${u.status}${u.configuration ? ", " + u.configuration : ""})`,
	}))
);
const sheetOptions = computed(() => {
	const chosen = (panel.value?.units || []).find((u) => u.name === unit.value);
	return chosen && chosen.cost_sheets.length
		? [
				{ value: "", label: "No cost sheet" },
				...chosen.cost_sheets.map((s) => ({ value: s.name, label: s.label })),
		  ]
		: [];
});
watch(unit, () => {
	sheet.value = "";
});

async function run(action, fallback) {
	error.value = "";
	try {
		return await action();
	} catch (e) {
		error.value = serverMessage(e, fallback);
		return null;
	}
}

async function load() {
	const result = await run(
		() => bookingApi.panel(props.lead),
		"The bookings could not be loaded."
	);
	if (result) panel.value = result;
}

async function book() {
	const result = await run(
		() => bookingApi.book(props.lead, unit.value, price.value, amount.value, sheet.value),
		"The unit could not be booked."
	);
	if (!result) return;
	panel.value = result;
	unit.value = sheet.value = "";
	price.value = amount.value = "";
	emit("changed");
}

async function cancel(deal) {
	const result = await run(
		() => bookingApi.cancel(deal, reason.value),
		"The booking could not be cancelled."
	);
	if (!result) return;
	panel.value = result;
	cancelling.value = reason.value = "";
	emit("changed");
}

onMounted(load);
defineExpose({ reload: load });
</script>
