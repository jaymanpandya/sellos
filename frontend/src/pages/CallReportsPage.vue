<template>
	<div data-testid="sellos-callreports-page">
		<PageHeader
			title="Call reports"
			text="What calling costs and how it performs, by agent and by purpose, for the dates you choose. Every figure opens the calls behind it."
			icon="lucide-phone-call"
		/>
		<FilterBar
			apply-label="Show report"
			clear-label="Last 30 days"
			@apply="load"
			@clear="reset"
		>
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
		</FilterBar>
		<div v-if="error" data-testid="sellos-callreports-error">
			<LoadError :message="error" @retry="load" />
		</div>
		<LoadingSkeleton v-else-if="!report" />
		<template v-else>
			<p class="mb-ui-md text-sm text-ink-muted" data-testid="sellos-callreports-range">
				Calls from {{ report.from_date }} to {{ report.to_date }}.
			</p>
			<EmptyState
				v-if="!report.totals.calls"
				title="No calls in these dates"
				text="No call was placed between these dates. Choose other dates."
				icon="lucide-phone-off"
			/>
			<template v-else>
				<div class="mb-ui-md grid grid-cols-2 gap-ui-md md:grid-cols-5">
					<div v-for="card in cards" :key="card.key">
						<StatCard
							:label="card.label"
							:value="card.value"
							:note="card.note"
							:icon="card.icon"
							:value-testid="`sellos-callreports-total-${card.key}`"
						/>
						<AppButton
							class="mt-ui-sm w-full"
							:data-testid="`sellos-callreports-open-${card.key}`"
							@click="open(card.label, card.figure)"
						>
							See calls
						</AppButton>
					</div>
				</div>
				<ListCard title="By agent" class="mb-ui-md">
					<table
						class="w-full text-left text-sm"
						data-testid="sellos-callreports-agents"
					>
						<thead class="text-xs text-ink-muted">
							<tr>
								<th scope="col" class="py-ui-sm">Agent</th>
								<th scope="col">Calls</th>
								<th scope="col">Connected</th>
								<th scope="col">Connect rate</th>
								<th scope="col">Talk time</th>
								<th scope="col">Cost</th>
								<th scope="col"><span class="sr-only">Calls</span></th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							<tr
								v-for="row in report.by_agent"
								:key="row.agent"
								data-testid="sellos-callreports-agent"
								:data-agent="row.agent"
								class="text-ink"
							>
								<td class="py-ui-sm">{{ row.agent_name }}</td>
								<td class="tabular-nums" data-col="calls">{{ row.calls }}</td>
								<td class="tabular-nums" data-col="connected">
									{{ row.connected }}
								</td>
								<td class="tabular-nums" data-col="rate">
									{{ row.connect_rate }}%
								</td>
								<td class="tabular-nums" data-col="talk">
									{{ talkTime(row.talk_seconds) }}
								</td>
								<td class="tabular-nums" data-col="cost">
									{{ rupees(row.cost) }}
								</td>
								<td>
									<AppButton
										data-testid="sellos-callreports-agent-open"
										@click="
											open(`Calls by ${row.agent_name}`, {
												agent: row.agent,
											})
										"
									>
										Calls
									</AppButton>
								</td>
							</tr>
						</tbody>
					</table>
				</ListCard>
				<ListCard title="By purpose" class="mb-ui-md">
					<table
						class="w-full text-left text-sm"
						data-testid="sellos-callreports-purposes"
					>
						<thead class="text-xs text-ink-muted">
							<tr>
								<th scope="col" class="py-ui-sm">Purpose</th>
								<th scope="col">Calls</th>
								<th scope="col">Connected</th>
								<th scope="col">Connect rate</th>
								<th scope="col">Talk time</th>
								<th scope="col">Cost</th>
								<th scope="col"><span class="sr-only">Calls</span></th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							<tr
								v-for="row in report.by_purpose"
								:key="row.purpose"
								data-testid="sellos-callreports-purpose"
								:data-purpose="row.purpose"
								class="text-ink"
							>
								<td class="py-ui-sm">{{ row.purpose }}</td>
								<td class="tabular-nums" data-col="calls">{{ row.calls }}</td>
								<td class="tabular-nums" data-col="connected">
									{{ row.connected }}
								</td>
								<td class="tabular-nums" data-col="rate">
									{{ row.connect_rate }}%
								</td>
								<td class="tabular-nums" data-col="talk">
									{{ talkTime(row.talk_seconds) }}
								</td>
								<td class="tabular-nums" data-col="cost">
									{{ rupees(row.cost) }}
								</td>
								<td>
									<AppButton
										data-testid="sellos-callreports-purpose-open"
										@click="
											open(`${row.purpose} calls`, { purpose: row.purpose })
										"
									>
										Calls
									</AppButton>
								</td>
							</tr>
						</tbody>
					</table>
				</ListCard>
				<ListCard title="Consent coverage" class="mb-ui-md">
					<p class="mb-ui-sm text-sm text-ink-muted">
						The consent status of each lead when it was called. A call is never stopped
						by it.
					</p>
					<ul
						class="divide-y divide-line-soft"
						data-testid="sellos-callreports-consents"
					>
						<li
							v-for="row in report.consent"
							:key="row.status"
							data-testid="sellos-callreports-consent"
							:data-status="row.status"
							class="flex items-center justify-between gap-ui-sm py-ui-sm text-sm text-ink"
						>
							<span>{{ row.status }}</span>
							<span class="tabular-nums" data-col="calls">
								{{ row.calls }} ({{ row.share }}%)
							</span>
							<AppButton
								data-testid="sellos-callreports-consent-open"
								@click="
									open(`${row.status} calls`, { consent_status: row.status })
								"
							>
								Calls
							</AppButton>
						</li>
					</ul>
				</ListCard>
			</template>
			<ListCard v-if="drill" :title="drill.title" class="mb-ui-md">
				<div data-testid="sellos-callreports-drill" :data-count="drill.calls.length">
					<p
						class="mb-ui-sm text-sm text-ink-muted"
						data-testid="sellos-callreports-drill-total"
					>
						{{ drill.calls.length }} calls,
						{{ talkTime(drill.totals.talk_seconds) }} talk time,
						{{ rupees(drill.totals.cost) }}
					</p>
					<EmptyState
						v-if="!drill.calls.length"
						title="No calls"
						text="No call matches this figure."
						icon="lucide-phone-off"
					/>
					<table v-else class="w-full text-left text-sm">
						<thead class="text-xs text-ink-muted">
							<tr>
								<th scope="col" class="py-ui-sm">Started</th>
								<th scope="col">Lead</th>
								<th scope="col">Agent</th>
								<th scope="col">Purpose</th>
								<th scope="col">State</th>
								<th scope="col">Talk time</th>
								<th scope="col">Cost</th>
								<th scope="col">Consent</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							<tr
								v-for="row in drill.calls"
								:key="row.name"
								data-testid="sellos-callreports-call"
								:data-call="row.name"
								class="text-ink"
							>
								<td class="py-ui-sm">{{ row.started_on.slice(0, 16) }}</td>
								<td>
									<router-link
										class="text-brand underline"
										:to="`/crm/leads/${row.lead}`"
									>
										{{ row.lead }}
									</router-link>
								</td>
								<td>{{ row.agent_name }}</td>
								<td>{{ row.purpose }}</td>
								<td>{{ row.state }}</td>
								<td class="tabular-nums">{{ talkTime(row.duration) }}</td>
								<td class="tabular-nums">{{ rupees(row.cost) }}</td>
								<td>{{ row.consent_status }}</td>
							</tr>
						</tbody>
					</table>
				</div>
			</ListCard>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import FilterBar from "../components/FilterBar.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import StatCard from "../components/StatCard.vue";
import { serverMessage } from "../crm/crmApi";
import { callsApi, rupees, talkTime } from "../reports/callsApi";

const range = reactive({ from_date: "", to_date: "" });
const report = ref(null);
const drill = ref(null);
const error = ref("");

// The cards, each with the filter that lists its calls. Cost and talk time list every call in the dates.
const cards = computed(() => {
	const t = report.value.totals;
	return [
		{ key: "calls", label: "Calls", value: t.calls, icon: "lucide-phone", figure: {} },
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
			icon: "lucide-timer",
			figure: {},
		},
		{
			key: "cost",
			label: "Cost",
			value: rupees(t.cost),
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
		range.from_date = report.value.from_date;
		range.to_date = report.value.to_date;
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
