<template>
	<PageTemplate data-testid="sellos-callreports-page">
		<template #header>
			<PageHeader
				title="Call reports"
				text="What calling costs and how it performs, by agent and by purpose, for the dates you choose. Every figure opens the calls behind it."
				icon="lucide-phone-call"
			/>
		</template>

		<template v-if="report && !error && report.totals.calls" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-callreports-stats" />
		</template>

		<template #filters>
			<FilterBar
				v-model:open="moreOpen"
				hide-search
				apply-label="Show report"
				clear-label="Last 30 days"
				more-testid="sellos-callreports-filters-toggle"
				:active="datesChanged"
				data-testid="sellos-callreports-filters"
				@apply="load"
				@clear="reset"
			>
				<template #more>
					<FormField
						v-model="range.from_date"
						type="date"
						label="From"
						data-testid="sellos-callreports-from"
					/>
					<FormField
						v-model="range.to_date"
						type="date"
						label="To"
						data-testid="sellos-callreports-to"
					/>
				</template>
			</FilterBar>
		</template>

		<div v-if="error" data-testid="sellos-callreports-error">
			<LoadError :message="error" @retry="load" />
		</div>
		<LoadingSkeleton v-else-if="!report" />
		<div v-else class="space-y-ui-md">
			<p class="text-sm text-ink-muted" data-testid="sellos-callreports-range">
				Calls from {{ report.from_date }} to {{ report.to_date }}.
			</p>
			<EmptyState
				v-if="!report.totals.calls"
				title="No calls in these dates"
				text="No call was placed between these dates. Choose other dates."
				icon="lucide-phone-off"
			/>
			<!-- The figure behind each card opens the calls it counts. -->
			<section v-else class="ui-card flex flex-wrap items-center gap-ui-sm">
				<h2 class="ui-card-heading mr-ui-sm">See the calls behind</h2>
				<AppButton
					v-for="card in cards"
					:key="card.key"
					:data-testid="`sellos-callreports-open-${card.key}`"
					@click="open(card.label, card.figure)"
				>
					{{ card.label }}
				</AppButton>
			</section>

			<div
				v-if="drill"
				data-testid="sellos-callreports-drill"
				:data-count="drill.calls.length"
			>
				<p
					class="mb-ui-sm text-sm text-ink-muted"
					data-testid="sellos-callreports-drill-total"
				>
					{{ drill.calls.length }} calls, {{ talkTime(drill.totals.talk_seconds) }} talk
					time,
					{{ rupees(drill.totals.cost) }}
				</p>
				<DataTable
					:title="drill.title"
					:columns="drillColumns"
					:rows="drill.calls"
					:page-size="200"
					empty-title="No calls"
					empty-text="No call matches this figure."
					empty-icon="lucide-phone-off"
					:row-attrs="(row) => ({ 'data-call': row.name })"
					testid="sellos-callreports-drill-table"
					row-testid="sellos-callreports-call"
					empty-testid="sellos-callreports-drill-empty"
				>
					<template #cell-started_on="{ row }">{{
						formatDateTime(row.started_on)
					}}</template>
					<template #cell-lead="{ row }">
						<router-link class="text-brand underline" :to="`/crm/leads/${row.lead}`">
							{{ row.lead }}
						</router-link>
					</template>
					<template #cell-duration="{ row }">{{ talkTime(row.duration) }}</template>
					<template #cell-cost="{ row }">{{ rupees(row.cost) }}</template>
				</DataTable>
			</div>

			<template v-if="report.totals.calls">
				<DataTable
					title="By agent"
					:columns="agentColumns"
					:rows="report.by_agent"
					row-key="agent"
					:row-attrs="(row) => ({ 'data-agent': row.agent })"
					:page-size="200"
					empty-title="No agents"
					testid="sellos-callreports-agents"
					row-testid="sellos-callreports-agent"
					empty-testid="sellos-callreports-agents-empty"
				>
					<template #cell-calls="{ row }">
						<span class="tabular-nums" data-col="calls">{{ row.calls }}</span>
					</template>
					<template #cell-connected="{ row }">
						<span class="tabular-nums" data-col="connected">{{ row.connected }}</span>
					</template>
					<template #cell-connect_rate="{ row }">
						<span class="tabular-nums" data-col="rate">{{ row.connect_rate }}%</span>
					</template>
					<template #cell-talk_seconds="{ row }">
						<span class="tabular-nums" data-col="talk">{{
							talkTime(row.talk_seconds)
						}}</span>
					</template>
					<template #cell-cost="{ row }">
						<span class="tabular-nums" data-col="cost">{{ rupees(row.cost) }}</span>
					</template>
					<template #cell-open="{ row }">
						<AppButton
							data-testid="sellos-callreports-agent-open"
							@click="open(`Calls by ${row.agent_name}`, { agent: row.agent })"
						>
							Calls
						</AppButton>
					</template>
				</DataTable>

				<DataTable
					title="By purpose"
					:columns="purposeColumns"
					:rows="report.by_purpose"
					row-key="purpose"
					:row-attrs="(row) => ({ 'data-purpose': row.purpose })"
					:page-size="200"
					empty-title="No purposes"
					testid="sellos-callreports-purposes"
					row-testid="sellos-callreports-purpose"
					empty-testid="sellos-callreports-purposes-empty"
				>
					<template #cell-calls="{ row }">
						<span class="tabular-nums" data-col="calls">{{ row.calls }}</span>
					</template>
					<template #cell-connected="{ row }">
						<span class="tabular-nums" data-col="connected">{{ row.connected }}</span>
					</template>
					<template #cell-connect_rate="{ row }">
						<span class="tabular-nums" data-col="rate">{{ row.connect_rate }}%</span>
					</template>
					<template #cell-talk_seconds="{ row }">
						<span class="tabular-nums" data-col="talk">{{
							talkTime(row.talk_seconds)
						}}</span>
					</template>
					<template #cell-cost="{ row }">
						<span class="tabular-nums" data-col="cost">{{ rupees(row.cost) }}</span>
					</template>
					<template #cell-open="{ row }">
						<AppButton
							data-testid="sellos-callreports-purpose-open"
							@click="open(`${row.purpose} calls`, { purpose: row.purpose })"
						>
							Calls
						</AppButton>
					</template>
				</DataTable>

				<p class="text-sm text-ink-muted">
					Consent coverage: the consent status of each lead when it was called. A call is
					never stopped by it.
				</p>
				<DataTable
					:title="`Consent coverage, ${report.totals.consent_coverage}% of calls to Consented leads`"
					:columns="consentColumns"
					:rows="report.consent"
					row-key="status"
					:row-attrs="(row) => ({ 'data-status': row.status })"
					:page-size="200"
					empty-title="No calls"
					testid="sellos-callreports-consents"
					row-testid="sellos-callreports-consent"
					empty-testid="sellos-callreports-consents-empty"
				>
					<template #cell-calls="{ row }">
						<span class="tabular-nums" data-col="calls"
							>{{ row.calls }} ({{ row.share }}%)</span
						>
					</template>
					<template #cell-open="{ row }">
						<AppButton
							data-testid="sellos-callreports-consent-open"
							@click="open(`${row.status} calls`, { consent_status: row.status })"
						>
							Calls
						</AppButton>
					</template>
				</DataTable>
			</template>
		</div>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import EmptyState from "../components/EmptyState.vue";
import FilterBar from "../components/FilterBar.vue";
import FormField from "../components/FormField.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import { serverMessage } from "../crm/crmApi";
import { formatDateTime } from "../format";
import { callsApi, rupees, talkTime } from "../reports/callsApi";

const range = reactive({ from_date: "", to_date: "" });
const report = ref(null);
const drill = ref(null);
const error = ref("");
// The dates are the one filter here, so the panel that holds them starts open.
const moreOpen = ref(true);
// The dates the page opened with, so Clear shows only when they have been changed.
const defaults = reactive({ from_date: "", to_date: "" });
const datesChanged = computed(
	() =>
		Boolean(defaults.from_date) &&
		(range.from_date !== defaults.from_date || range.to_date !== defaults.to_date)
);

// Call costs are rupees and paise, so they keep the two decimals of callsApi.rupees.
const kpis = computed(() =>
	cards.value.slice(0, 4).map((card) => ({
		label: card.label,
		value: card.value,
		caption: card.note,
		icon: card.icon,
		valueTestid: `sellos-callreports-total-${card.key}`,
	}))
);

const rateColumns = [
	{ key: "calls", label: "Calls", align: "right" },
	{ key: "connected", label: "Connected", align: "right" },
	{ key: "connect_rate", label: "Connect rate", align: "right" },
	{ key: "talk_seconds", label: "Talk time", align: "right" },
	{ key: "cost", label: "Cost", align: "right" },
	{ key: "open", label: "" },
];
const agentColumns = [{ key: "agent_name", label: "Agent", primary: true }, ...rateColumns];
const purposeColumns = [{ key: "purpose", label: "Purpose", primary: true }, ...rateColumns];
const consentColumns = [
	{ key: "status", label: "Consent status", primary: true },
	{ key: "calls", label: "Calls", align: "right" },
	{ key: "open", label: "" },
];
const drillColumns = [
	{ key: "started_on", label: "Started" },
	{ key: "lead", label: "Lead" },
	{ key: "agent_name", label: "Agent" },
	{ key: "purpose", label: "Purpose" },
	{ key: "state", label: "State" },
	{ key: "duration", label: "Talk time", align: "right" },
	{ key: "cost", label: "Cost", align: "right" },
	{ key: "consent_status", label: "Consent" },
];

// The cards, each with the filter that lists its calls. Cost and talk time list every call in the dates.
const cards = computed(() => {
	const t = report.value.totals;
	return [
		{
			key: "calls",
			label: "Calls",
			value: t.calls,
			note: "Placed in these dates",
			icon: "lucide-phone",
			figure: {},
		},
		{
			key: "connect-rate",
			label: "Connect rate",
			value: `${t.connect_rate}%`,
			note: `${t.connected} connected`,
			icon: "lucide-phone-incoming",
			figure: { connected: "1" },
		},
		{
			key: "talk-time",
			label: "Talk time",
			value: talkTime(t.talk_seconds),
			note: "Across all calls",
			icon: "lucide-timer",
			figure: {},
		},
		{
			key: "cost",
			label: "Cost",
			value: rupees(t.cost),
			note: "What the calls cost",
			icon: "lucide-indian-rupee",
			figure: {},
		},
		{
			key: "consent",
			label: "Consent coverage",
			value: `${t.consent_coverage}%`,
			note: "Calls to Consented leads",
			icon: "lucide-shield-check",
			figure: { consent_status: "Consented" },
		},
	];
});

async function load() {
	error.value = "";
	drill.value = null;
	try {
		report.value = await callsApi.report({ ...range });
		const fresh = !range.from_date && !range.to_date;
		range.from_date = report.value.from_date;
		range.to_date = report.value.to_date;
		if (fresh || !defaults.from_date) {
			defaults.from_date = range.from_date;
			defaults.to_date = range.to_date;
		}
	} catch (e) {
		error.value = serverMessage(e, "The report could not be loaded.");
	}
}

function reset() {
	range.from_date = "";
	range.to_date = "";
	load();
}

// The calls behind a figure, for the dates the report shows (not for dates typed since).
async function open(title, figure) {
	try {
		const found = await callsApi.calls(
			{ from_date: report.value.from_date, to_date: report.value.to_date },
			figure
		);
		drill.value = { title, ...found };
	} catch (e) {
		error.value = serverMessage(e, "The calls could not be loaded.");
	}
}

onMounted(load);
</script>
