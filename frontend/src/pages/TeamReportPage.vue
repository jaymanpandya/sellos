<template>
	<div class="max-w-3xl" data-testid="sellos-teamreport-page">
		<h1 class="ui-page-title">Team report</h1>
		<p class="mt-2 text-ink-muted">
			The open leads of your team, by agent and by stage. Only your own team is counted.
		</p>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-teamreport-error"
			class="mt-3 text-accent"
		>
			{{ error }}
		</p>
		<template v-if="report">
			<p class="mt-3 text-ink" data-testid="sellos-teamreport-total">
				Leads: {{ report.total }}
			</p>
			<p class="text-sm text-ink-muted" data-testid="sellos-teamreport-teams">
				Teams: {{ report.teams.join(", ") || "None" }}
			</p>
			<section class="mt-4 rounded-input border border-line bg-surface p-4">
				<h2 class="font-medium text-ink">By agent</h2>
				<ul data-testid="sellos-teamreport-agents">
					<li
						v-for="row in report.by_agent"
						:key="row.agent"
						data-testid="sellos-teamreport-agent"
						class="flex justify-between text-sm text-ink"
					>
						<span>{{ row.agent_name }}</span
						><span>{{ row.leads }}</span>
					</li>
				</ul>
			</section>
			<section class="mt-4 rounded-input border border-line bg-surface p-4">
				<h2 class="font-medium text-ink">By stage</h2>
				<ul data-testid="sellos-teamreport-stages">
					<li
						v-for="row in report.by_stage"
						:key="row.stage"
						class="flex justify-between text-sm text-ink"
					>
						<span>{{ row.stage || "No stage" }}</span
						><span>{{ row.leads }}</span>
					</li>
				</ul>
			</section>
		</template>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue";

import { teamsApi } from "../company/teamsApi";
import { serverMessage } from "../crm/crmApi";

const report = ref(null);
const error = ref("");

onMounted(async () => {
	try {
		report.value = await teamsApi.report();
	} catch (e) {
		error.value = serverMessage(e, "The report could not be loaded.");
	}
});
</script>
