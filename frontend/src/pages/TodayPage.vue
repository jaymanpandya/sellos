<template>
	<div data-testid="sellos-today">
		<p class="mb-ui-md text-sm text-ink-muted" data-testid="sellos-today-scope">
			{{ scopeNote }}
		</p>
		<LoadError
			v-if="error"
			class="mb-ui-md"
			data-testid="sellos-today-error"
			:message="error"
			@retry="onRetry"
		/>
		<LoadingSkeleton v-else-if="!view" />

		<template v-if="view">
			<div
				class="mb-ui-md grid grid-cols-2 gap-ui-md md:grid-cols-4"
				data-testid="sellos-today-counts"
			>
				<StatCard
					v-for="s in SECTIONS"
					:key="s.key"
					:label="s.label"
					:value="view.counts[s.key]"
					:icon="s.icon"
					:tone="s.tone"
					:value-testid="`sellos-today-count-${s.key}`"
				/>
			</div>

			<ListCard
				v-for="s in SECTIONS"
				:id="`today-${s.key}`"
				:key="s.key"
				:title="s.label"
				class="mb-ui-md"
				:data-testid="`sellos-today-section-${s.key}`"
			>
				<EmptyState
					v-if="!view[s.key].length"
					:data-testid="`sellos-today-empty-${s.key}`"
					:title="s.empty"
					:icon="s.icon"
				/>
				<template v-if="team">
					<div
						v-for="group in groups(s.key)"
						:key="group.agent"
						class="mt-ui-md"
						data-testid="sellos-today-agent"
						:data-agent="group.agent"
					>
						<h3 class="text-sm font-medium text-ink">
							{{ group.agent_name }} ({{ group.rows.length }})
						</h3>
						<ul class="mt-1 space-y-ui-sm">
							<TodayRow
								v-for="row in group.rows"
								:key="row.name || row.lead"
								:row="row"
								:section="s.key"
								:outcomes="outcomes"
								:full-numbers="Boolean(view.full_numbers)"
								@logged="load"
							>
								<VisitConfirm
									v-if="s.key === 'visits_tomorrow'"
									class="mt-ui-sm"
									:visit="row"
									:confirmations="confirmations"
									@changed="load"
								/>
							</TodayRow>
						</ul>
					</div>
				</template>
				<ul v-else class="space-y-ui-sm">
					<TodayRow
						v-for="row in view[s.key]"
						:key="row.name || row.lead"
						:row="row"
						:section="s.key"
						:outcomes="outcomes"
						:full-numbers="Boolean(view.full_numbers)"
						@logged="load"
					>
						<VisitConfirm
							v-if="s.key === 'visits_tomorrow'"
							class="mt-ui-sm"
							:visit="row"
							:confirmations="confirmations"
							@changed="load"
						/>
					</TodayRow>
				</ul>
			</ListCard>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import EmptyState from "../components/EmptyState.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import StatCard from "../components/StatCard.vue";
import VisitConfirm from "../components/VisitConfirm.vue";
import TodayRow from "../components/TodayRow.vue";
import { crmApi, serverMessage } from "../crm/crmApi";

// The Today screen (SOS-P1-26): what to do now, in four lists. A Sales Manager sees the same lists for
// the team, each grouped by agent. The counts come from the same answer as the lists.
const SECTIONS = [
	{
		key: "follow_ups",
		label: "Follow ups due and overdue",
		empty: "No follow ups due today.",
		icon: "lucide-clock-alert",
		tone: "danger",
	},
	{
		key: "new_leads",
		label: "New leads",
		empty: "No new leads waiting.",
		icon: "lucide-user-plus",
		tone: "success",
	},
	{
		key: "visits_today",
		label: "Site visits today",
		empty: "No site visits today.",
		icon: "lucide-calendar-check",
		tone: "info",
	},
	{
		key: "visits_tomorrow",
		label: "Tomorrow's visits to confirm",
		empty: "No site visits tomorrow.",
		icon: "lucide-calendar-clock",
		tone: "warning",
	},
];

const view = ref(null);
const outcomes = ref([]);
const confirmations = ref([]);
const error = ref("");

const team = computed(() => view.value?.scope === "team");
const scopeNote = computed(() =>
	team.value
		? "Your team's day, by agent."
		: view.value?.scope === "all"
		? "Everyone's day."
		: "Your day."
);

// The rows of one list grouped by agent, in the order of the list, and every agent of the team listed
// in name order (an agent with nothing has no group).
function groups(key) {
	const byAgent = new Map();
	for (const row of view.value[key]) {
		if (!byAgent.has(row.agent))
			byAgent.set(row.agent, { agent: row.agent, agent_name: row.agent_name, rows: [] });
		byAgent.get(row.agent).rows.push(row);
	}
	return [...byAgent.values()].sort((a, b) => a.agent_name.localeCompare(b.agent_name));
}

async function load() {
	error.value = "";
	try {
		view.value = await crmApi.todayScreen();
	} catch (e) {
		error.value = serverMessage(e, "Today could not be loaded.");
	}
}

async function init() {
	try {
		const [list, options] = await Promise.all([
			crmApi.listCallOutcomes(),
			crmApi.siteVisitOptions(),
		]);
		outcomes.value = list.outcomes;
		confirmations.value = options.confirmations;
	} catch (e) {
		error.value = serverMessage(e, "Today could not be loaded.");
	}
	await load();
}

const onRetry = init;
onMounted(init);
</script>
