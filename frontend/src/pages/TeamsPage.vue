<template>
	<PageTemplate data-testid="sellos-teams-page">
		<template #header>
			<PageHeader
				title="Sales teams"
				text="Group agents in teams and give each team a manager. A manager sees the leads of their own team and no other team's. An agent is in one team only."
				icon="lucide-users-round"
			>
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-teams-new"
					@click="openAdd"
				>
					<template #prefix
						><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
					/></template>
					Add team
				</AppButton>
			</PageHeader>
		</template>

		<template #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-teams-stats" />
		</template>

		<template #filters>
			<FilterBar
				v-model:search="search"
				search-label="Search teams"
				search-placeholder="Search teams"
				search-testid="sellos-teams-search"
				clear-testid="sellos-teams-filter-clear"
				:active="Boolean(search)"
				:chips="chips"
				data-testid="sellos-teams-filters"
				@clear="clearFilters"
				@remove-chip="removeChip"
			>
			</FilterBar>
		</template>

		<FormDrawer
			:open="adding"
			title="Add a team"
			text="Choose a manager and the agents who are not in a team yet."
			submit-label="Add team"
			testid="sellos-teams-form"
			submit-testid="sellos-teams-add"
			@close="adding = false"
			@submit="add"
		>
			<FormSection title="Team">
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
			</FormSection>
			<fieldset data-testid="sellos-teams-agents">
				<legend class="mb-ui-md w-full ui-text-strong">Agents</legend>
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
			<p v-if="error" role="alert" data-testid="sellos-teams-error" class="ui-text-error">
				{{ error }}
			</p>
		</FormDrawer>

		<p
			v-if="error && !adding"
			role="alert"
			data-testid="sellos-teams-error"
			class="mb-ui-md ui-text-error"
		>
			{{ error }}
		</p>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-teams-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<DataTable
			title="Teams"
			caption="Sales teams"
			:columns="columns"
			:rows="shown"
			:loading="!loaded"
			loading-label="Loading teams."
			empty-title="No teams yet"
			empty-text="Add the first team with Add team."
			empty-icon="lucide-users-round"
			testid="sellos-teams-list"
			row-testid="sellos-teams-team"
		>
			<template #cell-manager_name="{ row }">
				<span class="ui-text-secondary" data-testid="sellos-teams-manager">{{
					row.manager_name
				}}</span>
			</template>
			<template #cell-members="{ row }">
				<span class="ui-text-secondary" data-testid="sellos-teams-members">{{
					row.members.map((m) => m.full_name).join(", ") || "None yet"
				}}</span>
			</template>
			<template #cell-actions="{ row }">
				<AppButton type="button" data-testid="sellos-teams-remove" @click="remove(row)">
					Remove team
				</AppButton>
			</template>
		</DataTable>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import FilterBar from "../components/FilterBar.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
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
const adding = ref(false);
const kpis = computed(() => [
	{
		label: "Teams",
		value: teams.value.length,
		caption: "in your company",
		icon: "lucide-users-round",
	},
	{
		label: "Agents",
		value: agents.value.length,
		caption: "who can be in a team",
		icon: "lucide-user",
	},
	{
		label: "Agents in no team",
		value: freeAgents.value,
		caption: "can join a new team",
		icon: "lucide-user-x",
		tone: "warning",
	},
]);
const search = ref("");
const shown = computed(() => {
	const q = search.value.trim().toLowerCase();
	return teams.value.filter(
		(r) => (!q || `${r.team_name} ${r.manager_name}`.toLowerCase().includes(q)) && true
	);
});
const chips = computed(() => [
	...(search.value ? [{ key: "search", label: `Search: ${search.value}` }] : []),
]);
function clearFilters() {
	search.value = "";
}
function removeChip(key) {
	if (key === "search") search.value = "";
}

const columns = [
	{ key: "team_name", label: "Team", primary: true, sortable: true },
	{ key: "manager_name", label: "Manager", sortable: true },
	{ key: "members", label: "Agents", wrap: true, class: "min-w-[14rem]" },
	{ key: "actions", label: "Actions" },
];
function openAdd() {
	error.value = "";
	adding.value = true;
}
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
		adding.value = false;
	}, "The team could not be saved.");

const remove = (team) => run(() => teamsApi.remove(team.name), "The team could not be removed.");

onMounted(load);
</script>
