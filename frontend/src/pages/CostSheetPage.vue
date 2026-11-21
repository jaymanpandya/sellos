<template>
	<div data-testid="sellos-cost-sheet-page">
		<PageHeader
			:title="options ? `Cost sheet for unit ${options.unit.unit_number}` : 'Cost sheet'"
			text="The price from the price list in force, the charges, stamp duty, registration and GST, the total and the payment plan's schedule."
			icon="lucide-receipt-indian-rupee"
		/>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-cost-error"
			class="mb-ui-md text-sm text-accent"
		>
			{{ error }}
		</p>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-cost-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<div v-if="options" class="ui-card mb-ui-md" data-testid="sellos-cost-unit">
			<p class="text-sm text-ink">
				<router-link
					:to="{ name: 'project', params: { name: options.unit.project } }"
					class="ui-link font-medium"
					data-testid="sellos-cost-project-link"
				>
					{{ options.unit.project_name }}
				</router-link>
				, unit {{ options.unit.unit_number }},
				{{ options.unit.configuration || "no configuration" }},
				{{ options.unit.carpet_area }} sq ft carpet area, floor
				{{ options.unit.floor ?? "-" }}, {{ options.unit.parking }} parking.
			</p>
			<p
				v-if="options.price_list"
				class="text-sm text-ink-muted"
				data-testid="sellos-cost-list"
			>
				Price list in force: {{ options.price_list.title }} (from
				{{ options.price_list.effective_from }}),
				{{ rupees(options.price_list.base_rate) }} per sq ft.
			</p>
		</div>

		<p
			v-if="options && !options.ready"
			role="status"
			data-testid="sellos-cost-problem"
			class="ui-card mb-ui-md text-sm text-accent"
		>
			{{ options.problem }}
		</p>

		<form
			v-if="options && options.ready"
			class="ui-card mb-ui-md"
			data-testid="sellos-cost-form"
			@submit.prevent="make"
		>
			<h2 class="ui-card-heading mb-ui-md">Make a cost sheet</h2>
			<EmptyState
				v-if="!options.plans.length"
				title="No payment plan yet"
				text="A Company Admin adds a payment plan on the project page."
				icon="lucide-calendar-clock"
			/>
			<FormField
				v-else
				v-model="planName"
				type="select"
				label="Payment plan"
				:options="planOptions"
				required
				class="max-w-md"
				data-testid="sellos-cost-plan"
			/>
			<div v-if="optional.length" class="mt-ui-md space-y-ui-sm">
				<h3 class="text-sm font-medium text-ink">Charges to add</h3>
				<AppCheckbox
					v-for="c in optional"
					:key="c.charge_name"
					:model-value="!!chosen[c.charge_name]"
					:label="`${c.charge_name} (${rupees(c.value)}${
						c.basis === 'Rate per sq ft' ? ' per sq ft' : ''
					})`"
					:data-testid="`sellos-cost-charge-${c.charge_name}`"
					@update:model-value="chosen[c.charge_name] = $event"
				/>
			</div>
			<div class="mt-ui-md">
				<AppButton
					type="submit"
					variant="primary"
					:disabled="!options.plans.length"
					data-testid="sellos-cost-make"
				>
					Make cost sheet
				</AppButton>
			</div>
		</form>

		<ListCard v-if="sheet" :title="`Cost sheet ${sheet.name}`" class="mb-ui-md">
			<div data-testid="sellos-cost-sheet" :data-name="sheet.name">
				<p class="mb-ui-sm text-sm text-ink-muted">
					Price list {{ sheet.price_list_title }} (from {{ sheet.price_list_from }}),
					made by {{ sheet.made_by }}.
				</p>
				<ul class="divide-y divide-line-soft" data-testid="sellos-cost-lines">
					<li
						v-for="line in lines"
						:key="line.key"
						:data-testid="`sellos-cost-line-${line.key}`"
						class="flex justify-between gap-ui-md py-1 text-sm"
						:class="line.strong ? 'font-semibold text-ink' : 'text-ink'"
					>
						<span>{{ line.label }}</span>
						<span class="tabular-nums" data-testid="sellos-cost-amount">{{
							rupees(line.amount)
						}}</span>
					</li>
				</ul>
				<h3 class="mt-ui-md text-sm font-medium text-ink">
					{{ sheet.plan_name }} ({{ sheet.plan_type }})
				</h3>
				<ul class="divide-y divide-line-soft" data-testid="sellos-cost-schedule">
					<li
						v-for="(i, n) in sheet.instalments"
						:key="n"
						data-testid="sellos-cost-instalment"
						class="flex justify-between gap-ui-md py-1 text-sm text-ink"
					>
						<span
							>{{ i.label }}<span v-if="i.due_on"> ({{ i.due_on }})</span>,
							{{ i.percent }}%</span
						>
						<span class="tabular-nums" data-testid="sellos-cost-instalment-amount">{{
							rupees(i.amount)
						}}</span>
					</li>
				</ul>
				<p class="mt-ui-md">
					<a
						:href="costSheetApi.pdfUrl(sheet.name)"
						target="_blank"
						rel="noopener"
						class="ui-link font-medium"
						data-testid="sellos-cost-pdf"
					>
						Download the PDF
					</a>
				</p>
			</div>
		</ListCard>

		<ListCard v-if="options" title="Cost sheets of this unit">
			<EmptyState
				v-if="!options.sheets.length"
				title="No cost sheet yet"
				text="Make the first one above."
				icon="lucide-receipt-indian-rupee"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-cost-sheets">
				<li
					v-for="s in options.sheets"
					:key="s.name"
					data-testid="sellos-cost-sheet-row"
					:data-name="s.name"
					class="flex flex-wrap items-center gap-3 rounded-input border border-line-soft p-ui-md"
				>
					<span class="font-medium text-ink">{{ s.name }}</span>
					<span class="text-sm text-ink-muted">
						{{ rupees(s.total) }}, {{ s.plan_name }}, {{ s.price_list_title }}, by
						{{ s.made_by }}
					</span>
					<AppButton type="button" data-testid="sellos-cost-open" @click="open(s.name)">
						Open
					</AppButton>
				</li>
			</ul>
		</ListCard>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";

import AppButton from "../components/AppButton.vue";
import AppCheckbox from "../components/AppCheckbox.vue";
import EmptyState from "../components/EmptyState.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import { serverMessage } from "../crm/crmApi";
import { costSheetApi, rupees } from "../inventory/inventoryApi";

// A cost sheet made from a unit (SOS-P7-07). The agent chooses a payment plan and the optional charges; the
// server works the price out from the price list in force and the company's percentages, keeps it, and
// answers with the sheet as issued. Nothing is worked out in the browser.
const route = useRoute();
const options = ref(null);
const sheet = ref(null);
const planName = ref("");
const chosen = reactive({});
const error = ref("");
const loadError = ref("");

const optional = computed(() =>
	(options.value?.price_list?.charges || []).filter((c) => !c.always_apply)
);
const planOptions = computed(() =>
	(options.value?.plans || []).map((p) => ({ label: p.plan_name, value: p.name }))
);
const lines = computed(() => {
	const s = sheet.value;
	if (!s) return [];
	return [
		{
			key: "base",
			label: `Base price (${s.carpet_area} sq ft at ${rupees(s.base_rate)})`,
			amount: s.base_price,
		},
		...(s.floor_rise_amount
			? [
					{
						key: "rise",
						label: `Floor rise (floor ${s.floor})`,
						amount: s.floor_rise_amount,
					},
			  ]
			: []),
		...s.charges.map((c) => ({
			key: `charge-${c.charge_name}`,
			label: c.charge_name,
			amount: c.amount,
		})),
		{ key: "agreement", label: "Agreement value", amount: s.agreement_value, strong: true },
		{ key: "stamp", label: `Stamp duty (${s.stamp_duty_percent}%)`, amount: s.stamp_duty },
		{
			key: "registration",
			label: `Registration (${s.registration_percent}%)`,
			amount: s.registration,
		},
		{ key: "gst", label: `GST (${s.gst_percent}%)`, amount: s.gst },
		{ key: "total", label: "Total", amount: s.total, strong: true },
	];
});

async function load() {
	loadError.value = "";
	try {
		options.value = await costSheetApi.options(route.params.unit);
	} catch (e) {
		loadError.value = serverMessage(e, "The unit could not be loaded.");
	}
}

async function make() {
	error.value = "";
	try {
		sheet.value = await costSheetApi.make(
			route.params.unit,
			planName.value,
			optional.value.filter((c) => chosen[c.charge_name]).map((c) => c.charge_name)
		);
		options.value = await costSheetApi.options(route.params.unit);
	} catch (e) {
		error.value = serverMessage(e, "The cost sheet could not be made.");
	}
}

async function open(name) {
	error.value = "";
	try {
		sheet.value = await costSheetApi.get(name);
	} catch (e) {
		error.value = serverMessage(e, "The cost sheet could not be opened.");
	}
}

onMounted(load);
</script>
