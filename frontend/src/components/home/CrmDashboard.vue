<template>
	<div data-testid="sellos-dash">
		<LoadError
			v-if="error"
			class="mb-ui-md"
			data-testid="sellos-dash-error"
			:message="error"
			@retry="load"
		/>
		<LoadingSkeleton v-else-if="!loaded" variant="cards" :rows="4" />

		<template v-if="loaded">
			<div class="grid grid-cols-2 gap-ui-md lg:grid-cols-4" data-testid="sellos-dash-kpis">
				<StatCard
					v-for="kpi in kpis"
					:key="kpi.key"
					:label="kpi.label"
					:value="kpi.value"
					:note="kpi.note"
					:icon="kpi.icon"
					:tone="kpi.tone"
					:value-testid="`sellos-dash-kpi-${kpi.key}`"
				/>
			</div>

			<div class="mt-ui-md grid grid-cols-1 gap-ui-md lg:grid-cols-2">
				<ListCard title="Leads by stage" data-testid="sellos-dash-stages">
					<EmptyState
						v-if="!board.total"
						title="No leads in the pipeline yet."
						text="New leads appear here by stage as soon as they are added."
						icon="lucide-users"
					/>
					<StageBars v-else :columns="board.columns" />
				</ListCard>

				<ListCard title="Consent warnings" data-testid="sellos-dash-consent">
					<EmptyState
						v-if="!warned.length"
						title="No consent warnings."
						text="Every lead you can see has a live consent record."
						icon="lucide-shield-check"
					/>
					<template v-else>
						<p class="mb-ui-sm text-sm text-ink-muted">
							<b
								class="tabular-nums text-ink"
								data-testid="sellos-dash-consent-count"
								>{{ warned.length }}</b
							>
							of {{ queue.total }} leads carry a warning. Calls and messages still go
							ahead.
						</p>
						<ul class="divide-y divide-line-soft">
							<li
								v-for="row in warned.slice(0, 5)"
								:key="row.lead"
								class="flex items-center justify-between gap-ui-sm py-2"
								data-testid="sellos-dash-consent-row"
							>
								<router-link
									:to="`/crm/leads/${row.lead}`"
									class="ui-link min-w-0 truncate"
									>{{ row.lead_title }}</router-link
								>
								<StatusBadge
									:tone="row.consent_warning === 'red' ? 'danger' : 'warning'"
									:label="row.consent_status"
									:title="row.consent_message"
								/>
							</li>
						</ul>
					</template>
				</ListCard>

				<ListCard title="Follow ups overdue" data-testid="sellos-dash-overdue">
					<EmptyState
						v-if="!overdue.length"
						title="Nothing overdue."
						text="Every follow up due so far has been done."
						icon="lucide-clock-alert"
					/>
					<ul v-else class="divide-y divide-line-soft">
						<li
							v-for="row in overdue.slice(0, 5)"
							:key="row.name || row.lead"
							class="flex items-center justify-between gap-ui-sm py-2"
							data-testid="sellos-dash-overdue-row"
						>
							<router-link
								:to="`/crm/leads/${row.lead}`"
								class="ui-link min-w-0 truncate"
								>{{ row.lead_title }}</router-link
							>
							<span class="shrink-0 text-sm text-ink-muted">{{
								when(row.due_at || row.due_date)
							}}</span>
						</li>
					</ul>
				</ListCard>

				<ListCard title="Today's site visits" data-testid="sellos-dash-visits">
					<EmptyState
						v-if="!today.visits_today.length"
						title="No site visits today."
						text="Book one from a lead and it shows here on the day."
						icon="lucide-calendar-check"
					/>
					<ul v-else class="divide-y divide-line-soft">
						<li
							v-for="row in today.visits_today.slice(0, 5)"
							:key="row.name"
							class="flex items-center justify-between gap-ui-sm py-2"
							data-testid="sellos-dash-visit-row"
						>
							<router-link
								:to="`/crm/leads/${row.lead}`"
								class="ui-link min-w-0 truncate"
								>{{ row.lead_title }}</router-link
							>
							<span class="shrink-0 text-sm text-ink-muted">{{
								time(row.visit_datetime)
							}}</span>
						</li>
					</ul>
				</ListCard>
			</div>
		</template>
	</div>
</template>

<script setup>
// The Home dashboard of a Company Admin, Agent and Sales Manager. It reads three existing methods, as
// the Leads board, the Today screen and the caller queue do, and changes nothing. Each role sees what it
// may already see there: its own, its team's, or the whole company's.
import { computed, onMounted, ref } from "vue";

import EmptyState from "../EmptyState.vue";
import ListCard from "../ListCard.vue";
import LoadError from "../LoadError.vue";
import LoadingSkeleton from "../LoadingSkeleton.vue";
import StatCard from "../StatCard.vue";
import StatusBadge from "../StatusBadge.vue";
import StageBars from "./StageBars.vue";
import { crmApi, serverMessage } from "../../crm/crmApi";

const loaded = ref(false);
const error = ref("");
const board = ref({ columns: [], total: 0 });
const today = ref({ counts: {}, follow_ups: [], visits_today: [] });
const queue = ref({ total: 0, leads: [] });

const overdue = computed(() => today.value.follow_ups.filter((row) => row.state === "overdue"));
const warned = computed(() => queue.value.leads.filter((row) => row.consent_warning));
const kpis = computed(() => [
	{
		key: "leads",
		label: "Leads",
		value: board.value.total,
		note: "In the pipeline",
		icon: "lucide-users",
		tone: "",
	},
	{
		key: "new",
		label: "New leads",
		value: today.value.counts.new_leads || 0,
		note: "Waiting for a first call",
		icon: "lucide-user-plus",
		tone: "success",
	},
	{
		key: "overdue",
		label: "Follow ups overdue",
		value: overdue.value.length,
		note: `${today.value.counts.follow_ups || 0} due today or earlier`,
		icon: "lucide-clock-alert",
		tone: "danger",
	},
	{
		key: "visits",
		label: "Site visits today",
		value: today.value.counts.visits_today || 0,
		note: `${today.value.counts.visits_tomorrow || 0} tomorrow`,
		icon: "lucide-calendar-check",
		tone: "info",
	},
]);

function when(value) {
	const date = new Date(String(value).replace(" ", "T"));
	return Number.isNaN(date.getTime())
		? ""
		: date.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}
function time(value) {
	const date = new Date(String(value).replace(" ", "T"));
	return Number.isNaN(date.getTime())
		? ""
		: date.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
}

async function load() {
	error.value = "";
	loaded.value = false;
	try {
		const [b, t, q] = await Promise.all([
			crmApi.getBoard(),
			crmApi.todayScreen(),
			crmApi.callerQueue(),
		]);
		board.value = b;
		today.value = t;
		queue.value = q;
		loaded.value = true;
	} catch (e) {
		error.value = serverMessage(e, "The dashboard could not be loaded.");
	}
}

onMounted(load);
</script>
