<template>
	<div data-testid="sellos-teams-page">
		<PageHeader
			title="Sales teams"
			text="Group agents in teams and give each team a manager. A manager sees the leads of their own team and no other team's. An agent is in one team only."
			icon="lucide-users-round"
		/>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-teams-error"
			class="mb-ui-md text-sm text-accent"
		>
			{{ error }}
		</p>

		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-teams-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<div
			class="mb-ui-md grid grid-cols-2 gap-ui-md md:grid-cols-3"
			data-testid="sellos-teams-stats"
		>
			<StatCard label="Teams" :value="teams.length" icon="lucide-users-round" />
			<StatCard label="Agents" :value="agents.length" icon="lucide-user" />
			<StatCard
				label="Agents in no team"
				:value="freeAgents"
				icon="lucide-user-x"
				tone="warning"
			/>
		</div>

		<ListCard title="Teams">
			<EmptyState
				v-if="loaded && !loadError && !teams.length"
				title="No teams yet"
				text="Add the first team below."
				icon="lucide-users-round"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-teams-list">
				<li
					v-for="t in teams"
					:key="t.name"
					data-testid="sellos-teams-team"
					:data-name="t.name"
					class="rounded-input border border-line-soft p-ui-md"
				>
					<div class="flex items-center justify-between gap-3">
						<h3 class="font-medium text-ink">{{ t.team_name }}</h3>
						<AppButton
							type="button"
							data-testid="sellos-teams-remove"
							@click="remove(t)"
						>
							Remove team
						</AppButton>
					</div>
					<p class="text-sm text-ink-muted">
						Manager:
						<span data-testid="sellos-teams-manager">{{ t.manager_name }}</span>
					</p>
					<p class="text-sm text-ink-muted" data-testid="sellos-teams-members">
						Agents: {{ t.members.map((m) => m.full_name).join(", ") || "None yet" }}
					</p>
				</li>
			</ul>
		</ListCard>

		<form class="ui-card mt-ui-md" data-testid="sellos-teams-form" @submit.prevent="add">
			<h2 class="ui-card-heading mb-ui-md">Add a team</h2>
			<div class="grid grid-cols-1 gap-x-ui-md gap-y-ui-md md:grid-cols-2">
				<FormField
					v-model="form.team_name"
					label="Team name"
					required
					data-testid="sellos-teams-name"
				/>
				<FormField
					v-model="form.manager"
					type="select"
					label="Manager"
					required
					:options="managerOptions"
					data-testid="sellos-teams-manager-select"
				/>
			</div>
			<fieldset class="mt-ui-md" data-testid="sellos-teams-agents">
				<legend class="mb-1 text-sm font-medium text-ink">Agents</legend>
				<FormField
					v-for="a in agents"
					:key="a.name"
					type="checkbox"
					:model-value="form.members.includes(a.name)"
					:label="a.team ? `${a.full_name} (in ${a.team})` : a.full_name"
					:disabled="Boolean(a.team)"
					data-testid="sellos-teams-agent"
					:data-name="a.name"
					@update:model-value="toggleAgent(a.name, $event)"
				/>
			</fieldset>
			<div class="mt-ui-md">
				<AppButton type="submit" variant="primary" data-testid="sellos-teams-add">
					Add team
				</AppButton>
			</div>
		</form>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import StatCard from "../components/StatCard.vue";
import { teamsApi } from "../company/teamsApi";
import { serverMessage } from "../crm/crmApi";

// The Company Admin's teams (SOS-P1-18). Every change is saved on the server and the list read back.
const teams = ref([]);
const managers = ref([]);
const agents = ref([]);
const error = ref("");
const loadError = ref("");
const form = reactive({ team_name: "", manager: "", members: [] });

const loaded = ref(false);
const managerOptions = computed(() =>
	managers.value.map((m) => ({ label: m.full_name, value: m.name }))
);
const freeAgents = computed(() => agents.value.filter((a) => !a.team).length);
const toggleAgent = (name, on) => {
	form.members = on ? [...form.members, name] : form.members.filter((m) => m !== name);
};

async function load() {
	loadError.value = "";
	try {
		const data = await teamsApi.list();
		teams.value = data.teams;
		managers.value = data.managers || [];
		agents.value = data.agents || [];
	} catch (e) {
		loadError.value = serverMessage(e, "The teams could not be loaded.");
	} finally {
		loaded.value = true;
	}
}

async function run(action, fallback) {
	error.value = "";
	try {
		await action();
	} catch (e) {
		error.value = serverMessage(e, fallback);
	}
	await load();
}

const add = () =>
	run(async () => {
		await teamsApi.save({ ...form, members: [...form.members] });
		Object.assign(form, { team_name: "", manager: "", members: [] });
	}, "The team could not be saved.");

const remove = (team) => run(() => teamsApi.remove(team.name), "The team could not be removed.");

onMounted(load);
</script>
