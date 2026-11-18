<template>
	<div class="max-w-3xl" data-testid="sellos-teams-page">
		<h1 class="text-2xl font-semibold text-ink">Sales teams</h1>
		<p class="mt-2 text-ink-muted">
			Group agents in teams and give each team a manager. A manager sees the leads of their
			own team and no other team's. An agent is in one team only.
		</p>
		<p v-if="error" role="alert" data-testid="sellos-teams-error" class="mt-3 text-accent">
			{{ error }}
		</p>

		<ul class="mt-4 space-y-3" data-testid="sellos-teams-list">
			<li
				v-for="t in teams"
				:key="t.name"
				data-testid="sellos-teams-team"
				:data-name="t.name"
				class="rounded-input border border-line bg-surface p-4"
			>
				<div class="flex items-center justify-between gap-3">
					<h2 class="font-medium text-ink">{{ t.team_name }}</h2>
					<button
						type="button"
						class="btn"
						data-testid="sellos-teams-remove"
						@click="remove(t)"
					>
						Remove team
					</button>
				</div>
				<p class="text-sm text-ink-muted">
					Manager: <span data-testid="sellos-teams-manager">{{ t.manager_name }}</span>
				</p>
				<p class="text-sm text-ink-muted" data-testid="sellos-teams-members">
					Agents: {{ t.members.map((m) => m.full_name).join(", ") || "None yet" }}
				</p>
			</li>
		</ul>

		<form
			class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4"
			data-testid="sellos-teams-form"
			@submit.prevent="add"
		>
			<h2 class="font-medium text-ink">Add a team</h2>
			<input
				v-model="form.team_name"
				required
				placeholder="Team name"
				aria-label="Team name"
				data-testid="sellos-teams-name"
				class="field"
			/>
			<select
				v-model="form.manager"
				required
				aria-label="Manager"
				data-testid="sellos-teams-manager-select"
				class="field"
			>
				<option value="" disabled>Choose a manager</option>
				<option v-for="m in managers" :key="m.name" :value="m.name">
					{{ m.full_name }}
				</option>
			</select>
			<fieldset class="space-y-1" data-testid="sellos-teams-agents">
				<legend class="text-sm text-ink-muted">Agents</legend>
				<label
					v-for="a in agents"
					:key="a.name"
					class="flex items-center gap-2 text-sm text-ink"
				>
					<input
						v-model="form.members"
						type="checkbox"
						:value="a.name"
						:disabled="Boolean(a.team)"
						data-testid="sellos-teams-agent"
						:data-name="a.name"
					/>
					{{ a.full_name }}
					<span v-if="a.team" class="text-ink-muted">(in {{ a.team }})</span>
				</label>
			</fieldset>
			<button type="submit" class="btn" data-testid="sellos-teams-add">Add team</button>
		</form>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import { teamsApi } from "../company/teamsApi";
import { serverMessage } from "../crm/crmApi";

// The Company Admin's teams (SOS-P1-18). Every change is saved on the server and the list read back.
const teams = ref([]);
const managers = ref([]);
const agents = ref([]);
const error = ref("");
const form = reactive({ team_name: "", manager: "", members: [] });

async function load() {
	try {
		const data = await teamsApi.list();
		teams.value = data.teams;
		managers.value = data.managers || [];
		agents.value = data.agents || [];
	} catch (e) {
		error.value = serverMessage(e, "The teams could not be loaded.");
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
