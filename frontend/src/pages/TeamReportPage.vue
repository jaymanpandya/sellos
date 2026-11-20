<template>
	<div data-testid="sellos-teamreport-page">
		<PageHeader
			title="Team report"
			text="The open leads of your team, by agent and by stage. Only your own team is counted."
			icon="lucide-chart-column"
		/>
		<div v-if="error" data-testid="sellos-teamreport-error">
			<LoadError :message="error" @retry="load" />
		</div>
		<LoadingSkeleton v-else-if="!report" />
		<template v-else>
			<div class="mb-ui-md grid grid-cols-2 gap-ui-md md:grid-cols-3">
				<StatCard label="Open leads" :value="report.total" icon="lucide-users" />
				<StatCard label="Agents" :value="report.by_agent.length" icon="lucide-user" />
				<StatCard
					label="Stages in use"
					:value="report.by_stage.length"
					icon="lucide-layers"
				/>
			</div>
			<ListCard title="Your team" class="mb-ui-md">
				<p class="text-ink" data-testid="sellos-teamreport-total">
					Leads: {{ report.total }}
				</p>
				<p class="text-sm text-ink-muted" data-testid="sellos-teamreport-teams">
					Teams: {{ report.teams.join(", ") || "None" }}
				</p>
			</ListCard>
			<div class="grid grid-cols-1 gap-ui-md lg:grid-cols-2">
				<ListCard title="By agent">
					<EmptyState
						v-if="!report.by_agent.length"
						title="No open leads"
						text="No agent in your team has an open lead."
						icon="lucide-user"
					/>
					<ul data-testid="sellos-teamreport-agents" class="divide-y divide-line-soft">
						<li
							v-for="row in report.by_agent"
							:key="row.agent"
							data-testid="sellos-teamreport-agent"
							class="flex justify-between py-ui-sm text-sm text-ink"
						>
							<span>{{ row.agent_name }}</span
							><span class="tabular-nums">{{ row.leads }}</span>
						</li>
					</ul>
				</ListCard>
				<ListCard title="By stage">
					<EmptyState
						v-if="!report.by_stage.length"
						title="No open leads"
						text="There are no open leads in any stage."
						icon="lucide-layers"
					/>
					<ul data-testid="sellos-teamreport-stages" class="divide-y divide-line-soft">
						<li
							v-for="row in report.by_stage"
							:key="row.stage"
							class="flex justify-between py-ui-sm text-sm text-ink"
						>
							<span>{{ row.stage || "No stage" }}</span
							><span class="tabular-nums">{{ row.leads }}</span>
						</li>
					</ul>
				</ListCard>
			</div>
		</template>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue";

import EmptyState from "../components/EmptyState.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import StatCard from "../components/StatCard.vue";
import { teamsApi } from "../company/teamsApi";
import { serverMessage } from "../crm/crmApi";

const report = ref(null);
const error = ref("");

async function load() {
	error.value = "";
	try {
		report.value = await teamsApi.report();
	} catch (e) {
		error.value = serverMessage(e, "The report could not be loaded.");
	}
}

onMounted(load);
</script>
