<template>
	<PageTemplate data-testid="sellos-business-page">
		<template #header>
			<PageHeader
				title="Business reports"
				text="The lead funnel, source performance, agent productivity and the age of listings and mandates, for the dates you choose."
				icon="lucide-chart-column"
			/>
		</template>

		<template v-if="funnel && !error" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-business-stats" />
		</template>

		<template #filters>
			<FilterBar
				v-model:open="moreOpen"
				hide-search
				apply-label="Show reports"
				clear-label="Last 30 days"
				more-testid="sellos-business-filters-toggle"
				:active="datesChanged"
				data-testid="sellos-business-filters"
				@apply="load"
				@clear="reset"
			>
				<template #more>
					<FormField
						v-model="range.from_date"
						type="date"
						label="From"
						data-testid="sellos-business-from"
					/>
					<FormField
						v-model="range.to_date"
						type="date"
						label="To"
						data-testid="sellos-business-to"
					/>
				</template>
			</FilterBar>
		</template>

		<div v-if="error" data-testid="sellos-business-error">
			<LoadError :message="error" @retry="load" />
		</div>
		<LoadingSkeleton v-else-if="!funnel" />
		<div v-else class="space-y-ui-md">
			<p class="ui-text-muted" data-testid="sellos-business-range">
				From {{ funnel.from_date }} to {{ funnel.to_date }}.
			</p>

			<DataTable
				title="Lead funnel"
				:columns="funnelColumns"
				:rows="funnel.rows"
				row-key="stage"
				:row-attrs="(row) => ({ 'data-stage': row.stage })"
				:page-size="200"
				empty-title="No stages"
				testid="sellos-business-funnel"
				row-testid="sellos-business-stage"
				empty-testid="sellos-business-funnel-empty"
			>
				<template #cell-in_stage="{ row }">
					<span class="tabular-nums" data-col="in_stage">{{ row.in_stage }}</span>
				</template>
				<template #cell-reached="{ row }">
					<span class="tabular-nums" data-col="reached">{{ row.reached ?? "" }}</span>
				</template>
				<template #cell-conversion="{ row }">
					<span class="tabular-nums" data-col="conversion">{{
						row.conversion === null ? "" : `${row.conversion}%`
					}}</span>
				</template>
			</DataTable>

			<DataTable
				title="Source performance"
				:columns="sourceColumns"
				:rows="sources.rows"
				row-key="source"
				:row-attrs="(row) => ({ 'data-source': row.source })"
				:page-size="200"
				empty-title="No leads in these dates"
				empty-text="No lead was created between these dates. Choose other dates."
				empty-icon="lucide-users"
				testid="sellos-business-sources"
				row-testid="sellos-business-source"
				empty-testid="sellos-business-sources-empty"
			>
				<template #cell-leads="{ row }">
					<span class="tabular-nums" data-col="leads">{{ row.leads }}</span>
				</template>
				<template #cell-won="{ row }">
					<span class="tabular-nums" data-col="won">{{ row.won }}</span>
				</template>
				<template #cell-lost="{ row }">
					<span class="tabular-nums" data-col="lost">{{ row.lost }}</span>
				</template>
				<template #cell-conversion="{ row }">
					<span class="tabular-nums" data-col="conversion">{{ row.conversion }}%</span>
				</template>
			</DataTable>

			<DataTable
				title="Agent productivity"
				:columns="agentColumns"
				:rows="agents.rows"
				row-key="agent"
				:row-attrs="(row) => ({ 'data-agent': row.agent })"
				:page-size="200"
				empty-title="No work in these dates"
				empty-text="No agent has a lead, call, visit, follow up or deal in these dates."
				empty-icon="lucide-user"
				testid="sellos-business-agents"
				row-testid="sellos-business-agent"
				empty-testid="sellos-business-agents-empty"
			>
				<template #cell-leads="{ row }">
					<span class="tabular-nums" data-col="leads">{{ row.leads }}</span>
				</template>
				<template #cell-calls="{ row }">
					<span class="tabular-nums" data-col="calls">{{ row.calls }}</span>
				</template>
				<template #cell-connected="{ row }">
					<span class="tabular-nums" data-col="connected">{{ row.connected }}</span>
				</template>
				<template #cell-talk_seconds="{ row }">
					<span class="tabular-nums" data-col="talk">{{
						talkTime(row.talk_seconds)
					}}</span>
				</template>
				<template #cell-visits_done="{ row }">
					<span class="tabular-nums" data-col="visits">{{ row.visits_done }}</span>
				</template>
				<template #cell-follow_ups_done="{ row }">
					<span class="tabular-nums" data-col="follow_ups">{{
						row.follow_ups_done
					}}</span>
				</template>
				<template #cell-deals="{ row }">
					<span class="tabular-nums" data-col="deals">{{ row.deals }}</span>
				</template>
			</DataTable>

			<div class="grid grid-cols-1 gap-ui-md lg:grid-cols-2">
				<DataTable
					title="Listing ageing"
					:columns="listingColumns"
					:rows="ageing.listings.bands"
					row-key="band"
					:row-attrs="(row) => ({ 'data-band': row.band })"
					empty-title="No listings"
					testid="sellos-business-listings"
					row-testid="sellos-business-listing-band"
					empty-testid="sellos-business-listings-empty"
				>
					<template #cell-count="{ row }">
						<span class="tabular-nums" data-col="count">{{ row.count }}</span>
					</template>
					<template #cell-published="{ row }">
						<span class="tabular-nums" data-col="published">{{ row.published }}</span>
					</template>
					<template #cell-asking="{ row }">
						<span class="tabular-nums" data-col="asking">{{
							formatBudget(row.asking)
						}}</span>
					</template>
				</DataTable>
				<DataTable
					title="Mandate ageing"
					:columns="mandateColumns"
					:rows="ageing.mandates.bands"
					row-key="band"
					:row-attrs="(row) => ({ 'data-band': row.band })"
					empty-title="No mandates"
					testid="sellos-business-mandates"
					row-testid="sellos-business-mandate-band"
					empty-testid="sellos-business-mandates-empty"
				>
					<template #cell-count="{ row }">
						<span class="tabular-nums" data-col="count">{{ row.count }}</span>
					</template>
					<template #cell-signed="{ row }">
						<span class="tabular-nums" data-col="signed">{{ row.signed }}</span>
					</template>
					<template #cell-expired="{ row }">
						<span class="tabular-nums" data-col="expired">{{ row.expired }}</span>
					</template>
				</DataTable>
			</div>
		</div>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import DataTable from "../components/DataTable.vue";
import FilterBar from "../components/FilterBar.vue";
import FormField from "../components/FormField.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import { serverMessage } from "../crm/crmApi";
import { formatBudget } from "../format";
import { businessApi } from "../reports/businessApi";
import { talkTime } from "../reports/callsApi";

const range = reactive({ from_date: "", to_date: "" });
const funnel = ref(null);
const sources = ref(null);
const agents = ref(null);
const ageing = ref(null);
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

const kpis = computed(() => [
	{
		label: "Leads",
		value: funnel.value.totals.leads,
		caption: "Created in these dates",
		icon: "lucide-users",
		valueTestid: "sellos-business-leads",
	},
	{
		label: "Won",
		value: funnel.value.totals.won,
		caption: "In these dates",
		icon: "lucide-trophy",
		tone: "success",
		valueTestid: "sellos-business-won",
	},
	{
		label: "Lost",
		value: funnel.value.totals.lost,
		caption: "In these dates",
		icon: "lucide-x",
		tone: "danger",
		valueTestid: "sellos-business-lost",
	},
	{
		label: "Conversion",
		value: `${funnel.value.totals.conversion}%`,
		caption: "Of all leads",
		icon: "lucide-percent",
		valueTestid: "sellos-business-conversion",
	},
]);

const funnelColumns = [
	{ key: "stage", label: "Stage", primary: true },
	{ key: "in_stage", label: "In it now", align: "right" },
	{ key: "reached", label: "Reached it", align: "right" },
	{ key: "conversion", label: "Of all leads", align: "right" },
];
const sourceColumns = [
	{ key: "label", label: "Source", primary: true },
	{ key: "leads", label: "Leads", align: "right" },
	{ key: "won", label: "Won", align: "right" },
	{ key: "lost", label: "Lost", align: "right" },
	{ key: "conversion", label: "Conversion", align: "right" },
];
const agentColumns = [
	{ key: "agent_name", label: "Agent", primary: true },
	{ key: "leads", label: "Leads", align: "right" },
	{ key: "calls", label: "Calls", align: "right" },
	{ key: "connected", label: "Connected", align: "right" },
	{ key: "talk_seconds", label: "Talk time", align: "right" },
	{ key: "visits_done", label: "Visits done", align: "right" },
	{ key: "follow_ups_done", label: "Follow ups done", align: "right" },
	{ key: "deals", label: "Deals", align: "right" },
];
const listingColumns = [
	{ key: "band", label: "Age", primary: true },
	{ key: "count", label: "Listings", align: "right" },
	{ key: "published", label: "Published", align: "right" },
	{ key: "asking", label: "Asking price", align: "right" },
];
const mandateColumns = [
	{ key: "band", label: "Age", primary: true },
	{ key: "count", label: "Mandates", align: "right" },
	{ key: "signed", label: "Signed", align: "right" },
	{ key: "expired", label: "Expired", align: "right" },
];

async function load() {
	error.value = "";
	try {
		const [f, s, a, g] = await Promise.all([
			businessApi.funnel({ ...range }),
			businessApi.sources({ ...range }),
			businessApi.agents({ ...range }),
			businessApi.ageing({ ...range }),
		]);
		const fresh = !range.from_date && !range.to_date;
		funnel.value = f;
		sources.value = s;
		agents.value = a;
		ageing.value = g;
		range.from_date = f.from_date;
		range.to_date = f.to_date;
		if (fresh || !defaults.from_date) {
			defaults.from_date = f.from_date;
			defaults.to_date = f.to_date;
		}
	} catch (e) {
		error.value = serverMessage(e, "The reports could not be loaded.");
	}
}

function reset() {
	range.from_date = "";
	range.to_date = "";
	load();
}

onMounted(load);
</script>
