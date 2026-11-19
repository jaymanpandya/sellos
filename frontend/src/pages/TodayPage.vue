<template>
	<div data-testid="sellos-today">
		<h2 class="text-xl font-semibold text-ink">Today</h2>
		<p class="mt-1 text-sm text-ink-muted" data-testid="sellos-today-scope">{{ scopeNote }}</p>
		<p v-if="error" role="alert" data-testid="sellos-today-error" class="mt-3 text-accent">
			{{ error }}
		</p>

		<template v-if="view">
			<ul
				class="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4"
				data-testid="sellos-today-counts"
			>
				<li
					v-for="s in SECTIONS"
					:key="s.key"
					class="rounded-input border border-line bg-surface p-3"
				>
					<a :href="`#today-${s.key}`" class="block text-sm text-ink-muted">{{
						s.label
					}}</a>
					<span
						class="text-2xl font-semibold text-ink"
						:data-testid="`sellos-today-count-${s.key}`"
						>{{ view.counts[s.key] }}</span
					>
				</li>
			</ul>

			<section
				v-for="s in SECTIONS"
				:id="`today-${s.key}`"
				:key="s.key"
				class="mt-4 rounded-input border border-line bg-surface p-4"
				:data-testid="`sellos-today-section-${s.key}`"
			>
				<h3 class="font-medium text-ink">{{ s.label }}</h3>
				<p
					v-if="!view[s.key].length"
					:data-testid="`sellos-today-empty-${s.key}`"
					class="mt-2 text-ink-muted"
				>
					{{ s.empty }}
				</p>
				<template v-if="team">
					<div
						v-for="group in groups(s.key)"
						:key="group.agent"
						class="mt-3"
						data-testid="sellos-today-agent"
						:data-agent="group.agent"
					>
						<h4 class="text-sm font-medium text-ink">
							{{ group.agent_name }} ({{ group.rows.length }})
						</h4>
						<ul class="mt-1 space-y-2">
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
									class="mt-2"
									:visit="row"
									:confirmations="confirmations"
									@changed="load"
								/>
							</TodayRow>
						</ul>
					</div>
				</template>
				<ul v-else class="mt-2 space-y-2">
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
							class="mt-2"
							:visit="row"
							:confirmations="confirmations"
							@changed="load"
						/>
					</TodayRow>
				</ul>
			</section>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import VisitConfirm from "../components/VisitConfirm.vue";
import TodayRow from "../components/TodayRow.vue";
import { crmApi, serverMessage } from "../crm/crmApi";

// The Today screen (SOS-P1-26): what to do now, in four lists. A Sales Manager sees the same lists for
// the team, each grouped by agent. The counts come from the same answer as the lists.
const SECTIONS = [
	{ key: "follow_ups", label: "Follow ups due and overdue", empty: "No follow ups due today." },
	{ key: "new_leads", label: "New leads", empty: "No new leads waiting." },
	{ key: "visits_today", label: "Site visits today", empty: "No site visits today." },
	{
		key: "visits_tomorrow",
		label: "Tomorrow's visits to confirm",
		empty: "No site visits tomorrow.",
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

onMounted(async () => {
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
});
</script>
