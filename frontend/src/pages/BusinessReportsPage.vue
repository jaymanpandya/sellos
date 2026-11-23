<template>
	<div data-testid="sellos-business-page">
		<PageHeader
			title="Business reports"
			text="The lead funnel, source performance, agent productivity and the age of listings and mandates, for the dates you choose."
			icon="lucide-chart-column"
		/>
		<FilterBar
			apply-label="Show reports"
			clear-label="Last 30 days"
			@apply="load"
			@clear="reset"
		>
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
		</FilterBar>
		<div v-if="error" data-testid="sellos-business-error">
			<LoadError :message="error" @retry="load" />
		</div>
		<LoadingSkeleton v-else-if="!funnel" />
		<template v-else>
			<p class="mb-ui-md text-sm text-ink-muted" data-testid="sellos-business-range">
				From {{ funnel.from_date }} to {{ funnel.to_date }}.
			</p>
			<div class="mb-ui-md grid grid-cols-2 gap-ui-md md:grid-cols-4">
				<StatCard
					label="Leads"
					:value="funnel.totals.leads"
					icon="lucide-users"
					value-testid="sellos-business-leads"
				/>
				<StatCard
					label="Won"
					:value="funnel.totals.won"
					icon="lucide-trophy"
					value-testid="sellos-business-won"
				/>
				<StatCard
					label="Lost"
					:value="funnel.totals.lost"
					icon="lucide-x"
					value-testid="sellos-business-lost"
				/>
				<StatCard
					label="Conversion"
					:value="`${funnel.totals.conversion}%`"
					icon="lucide-percent"
					value-testid="sellos-business-conversion"
				/>
			</div>
			<ListCard title="Lead funnel" class="mb-ui-md">
				<table class="w-full text-left text-sm" data-testid="sellos-business-funnel">
					<thead class="text-xs text-ink-muted">
						<tr>
							<th scope="col" class="py-ui-sm">Stage</th>
							<th scope="col">In it now</th>
							<th scope="col">Reached it</th>
							<th scope="col">Of all leads</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-line-soft">
						<tr
							v-for="row in funnel.rows"
							:key="row.stage"
							data-testid="sellos-business-stage"
							:data-stage="row.stage"
							class="text-ink"
						>
							<td class="py-ui-sm">{{ row.stage }}</td>
							<td class="tabular-nums" data-col="in_stage">{{ row.in_stage }}</td>
							<td class="tabular-nums" data-col="reached">
								{{ row.reached ?? "" }}
							</td>
							<td class="tabular-nums" data-col="conversion">
								{{ row.conversion === null ? "" : `${row.conversion}%` }}
							</td>
						</tr>
					</tbody>
				</table>
			</ListCard>
			<ListCard title="Source performance" class="mb-ui-md">
				<EmptyState
					v-if="!sources.rows.length"
					title="No leads in these dates"
					text="No lead was created between these dates. Choose other dates."
					icon="lucide-users"
				/>
				<table
					v-else
					class="w-full text-left text-sm"
					data-testid="sellos-business-sources"
				>
					<thead class="text-xs text-ink-muted">
						<tr>
							<th scope="col" class="py-ui-sm">Source</th>
							<th scope="col">Leads</th>
							<th scope="col">Won</th>
							<th scope="col">Lost</th>
							<th scope="col">Conversion</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-line-soft">
						<tr
							v-for="row in sources.rows"
							:key="row.source"
							data-testid="sellos-business-source"
							:data-source="row.source"
							class="text-ink"
						>
							<td class="py-ui-sm">{{ row.label }}</td>
							<td class="tabular-nums" data-col="leads">{{ row.leads }}</td>
							<td class="tabular-nums" data-col="won">{{ row.won }}</td>
							<td class="tabular-nums" data-col="lost">{{ row.lost }}</td>
							<td class="tabular-nums" data-col="conversion">
								{{ row.conversion }}%
							</td>
						</tr>
					</tbody>
				</table>
			</ListCard>
			<ListCard title="Agent productivity" class="mb-ui-md">
				<EmptyState
					v-if="!agents.rows.length"
					title="No work in these dates"
					text="No agent has a lead, call, visit, follow up or deal in these dates."
					icon="lucide-user"
				/>
				<table
					v-else
					class="w-full text-left text-sm"
					data-testid="sellos-business-agents"
				>
					<thead class="text-xs text-ink-muted">
						<tr>
							<th scope="col" class="py-ui-sm">Agent</th>
							<th scope="col">Leads</th>
							<th scope="col">Calls</th>
							<th scope="col">Connected</th>
							<th scope="col">Talk time</th>
							<th scope="col">Visits done</th>
							<th scope="col">Follow ups done</th>
							<th scope="col">Deals</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-line-soft">
						<tr
							v-for="row in agents.rows"
							:key="row.agent"
							data-testid="sellos-business-agent"
							:data-agent="row.agent"
							class="text-ink"
						>
							<td class="py-ui-sm">{{ row.agent_name }}</td>
							<td class="tabular-nums" data-col="leads">{{ row.leads }}</td>
							<td class="tabular-nums" data-col="calls">{{ row.calls }}</td>
							<td class="tabular-nums" data-col="connected">{{ row.connected }}</td>
							<td class="tabular-nums" data-col="talk">
								{{ talkTime(row.talk_seconds) }}
							</td>
							<td class="tabular-nums" data-col="visits">{{ row.visits_done }}</td>
							<td class="tabular-nums" data-col="follow_ups">
								{{ row.follow_ups_done }}
							</td>
							<td class="tabular-nums" data-col="deals">{{ row.deals }}</td>
						</tr>
					</tbody>
				</table>
			</ListCard>
			<div class="grid grid-cols-1 gap-ui-md lg:grid-cols-2">
				<ListCard title="Listing ageing">
					<table class="w-full text-left text-sm" data-testid="sellos-business-listings">
						<thead class="text-xs text-ink-muted">
							<tr>
								<th scope="col" class="py-ui-sm">Age</th>
								<th scope="col">Listings</th>
								<th scope="col">Published</th>
								<th scope="col">Asking price</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							<tr
								v-for="row in ageing.listings.bands"
								:key="row.band"
								data-testid="sellos-business-listing-band"
								:data-band="row.band"
								class="text-ink"
							>
								<td class="py-ui-sm">{{ row.band }}</td>
								<td class="tabular-nums" data-col="count">{{ row.count }}</td>
								<td class="tabular-nums" data-col="published">
									{{ row.published }}
								</td>
								<td class="tabular-nums" data-col="asking">
									{{ rupees(row.asking) }}
								</td>
							</tr>
						</tbody>
					</table>
				</ListCard>
				<ListCard title="Mandate ageing">
					<table class="w-full text-left text-sm" data-testid="sellos-business-mandates">
						<thead class="text-xs text-ink-muted">
							<tr>
								<th scope="col" class="py-ui-sm">Age</th>
								<th scope="col">Mandates</th>
								<th scope="col">Signed</th>
								<th scope="col">Expired</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							<tr
								v-for="row in ageing.mandates.bands"
								:key="row.band"
								data-testid="sellos-business-mandate-band"
								:data-band="row.band"
								class="text-ink"
							>
								<td class="py-ui-sm">{{ row.band }}</td>
								<td class="tabular-nums" data-col="count">{{ row.count }}</td>
								<td class="tabular-nums" data-col="signed">{{ row.signed }}</td>
								<td class="tabular-nums" data-col="expired">{{ row.expired }}</td>
							</tr>
						</tbody>
					</table>
				</ListCard>
			</div>
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
import { serverMessage } from "../crm/crmApi";
import { businessApi } from "../reports/businessApi";
import { rupees, talkTime } from "../reports/callsApi";

const range = reactive({ from_date: "", to_date: "" });
const funnel = ref(null);
const sources = ref(null);
const agents = ref(null);
const ageing = ref(null);
const error = ref("");

async function load() {
	error.value = "";
	try {
		const [f, s, a, g] = await Promise.all([
			businessApi.funnel({ ...range }),
			businessApi.sources({ ...range }),
			businessApi.agents({ ...range }),
			businessApi.ageing({ ...range }),
		]);
		funnel.value = f;
		sources.value = s;
		agents.value = a;
		ageing.value = g;
		range.from_date = f.from_date;
		range.to_date = f.to_date;
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
