<template>
	<PageTemplate data-testid="sellos-cost-sheet-page">
		<template #header>
			<PageHeader
				:title="options ? `Cost sheet for unit ${options.unit.unit_number}` : 'Cost sheet'"
				text="The price from the price list in force, the charges, stamp duty, registration and GST, the total and the payment plan's schedule."
				icon="lucide-receipt-indian-rupee"
			/>
		</template>

		<template v-if="sheet" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-cost-stats" />
		</template>

		<p
			v-if="error"
			role="alert"
			data-testid="sellos-cost-error"
			class="mb-ui-md text-sm text-danger"
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
				{{ formatDate(options.price_list.effective_from) }}),
				{{ formatMoney(options.price_list.base_rate) }} per sq ft.
			</p>
		</div>

		<p
			v-if="options && !options.ready"
			role="status"
			data-testid="sellos-cost-problem"
			class="ui-card mb-ui-md text-sm text-danger"
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
					:label="`${c.charge_name} (${formatMoney(c.value)}${
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
					Price list {{ sheet.price_list_title }} (from
					{{ formatDate(sheet.price_list_from) }}), made by {{ sheet.made_by }}.
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
							formatMoney(line.amount)
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
							>{{ i.label
							}}<span v-if="i.due_on"> ({{ formatDate(i.due_on) }})</span>,
							{{ i.percent }}%</span
						>
						<span class="tabular-nums" data-testid="sellos-cost-instalment-amount">{{
							formatMoney(i.amount)
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

		<DataTable
			v-if="options"
			title="Cost sheets of this unit"
			caption="Cost sheets of this unit"
			:columns="sheetColumns"
			:rows="options.sheets"
			:row-name="(r) => r.name"
			empty-title="No cost sheet yet"
			empty-text="Make the first one above."
			empty-icon="lucide-receipt-indian-rupee"
			testid="sellos-cost-sheets"
			row-testid="sellos-cost-sheet-row"
		>
			<template #cell-total="{ row }">{{ formatMoney(row.total) }}</template>
			<template #cell-open="{ row }">
				<AppButton type="button" data-testid="sellos-cost-open" @click="open(row.name)">
					Open
				</AppButton>
			</template>
		</DataTable>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";

import AppButton from "../components/AppButton.vue";
import AppCheckbox from "../components/AppCheckbox.vue";
import DataTable from "../components/DataTable.vue";
import EmptyState from "../components/EmptyState.vue";
import FormField from "../components/FormField.vue";
import KpiStrip from "../components/KpiStrip.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import { serverMessage } from "../crm/crmApi";
import { formatDate, formatMoney } from "../format";
import { costSheetApi } from "../inventory/inventoryApi";

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

const kpis = computed(() => {
	const s = sheet.value;
	if (!s) return [];
	return [
		{
			label: "Base price",
			value: formatMoney(s.base_price),
			caption: `${s.carpet_area} sq ft carpet area`,
			icon: "lucide-ruler",
		},
		{
			label: "Agreement value",
			value: formatMoney(s.agreement_value),
			caption: "price and charges",
			icon: "lucide-file-text",
		},
		{
			label: "Total",
			value: formatMoney(s.total),
			caption: "with stamp duty, registration and GST",
			icon: "lucide-receipt-indian-rupee",
			tone: "success",
		},
	];
});
const sheetColumns = [
	{ key: "name", label: "Cost sheet", primary: true },
	{
		key: "total",
		label: "Total",
		align: "right",
		sortable: true,
		sortValue: (r) => Number(r.total || 0),
	},
	{ key: "plan_name", label: "Payment plan" },
	{ key: "price_list_title", label: "Price list" },
	{ key: "made_by", label: "Made by" },
	{ key: "open", label: "" },
];

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
			label: `Base price (${s.carpet_area} sq ft at ${formatMoney(s.base_rate)})`,
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
