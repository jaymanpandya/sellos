<template>
	<PageTemplate data-testid="sellos-assignment-page">
		<template #header>
			<PageHeader
				title="Lead assignment"
				text="Every new lead goes to an agent at once. Rules are tried from the lowest order up, and a lead no rule matches goes to the default team."
				icon="lucide-shuffle"
			>
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-assignment-new"
					@click="openAdd"
				>
					<template #prefix
						><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
					/></template>
					Add rule
				</AppButton>
			</PageHeader>
		</template>

		<template #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-assignment-stats" />
		</template>

		<LoadError
			v-if="error && !adding"
			class="mb-ui-md"
			data-testid="sellos-assignment-error"
			:message="error"
			@retry="load"
		/>

		<ListCard title="Default team" class="mb-ui-md">
			<FormField
				:model-value="defaultTeam"
				type="select"
				label="Default team"
				:options="defaultTeamOptions"
				data-testid="sellos-assignment-default"
				@update:model-value="saveDefault"
			/>
		</ListCard>

		<DataTable
			title="Rules"
			caption="Assignment rules"
			:columns="columns"
			:rows="rules"
			:loading="loading"
			loading-label="Loading rules."
			empty-title="No rules yet."
			empty-text="Every lead goes to the default team until a rule is added."
			empty-icon="lucide-shuffle"
			testid="sellos-assignment-rules"
			row-testid="sellos-assignment-rule"
		>
			<template #cell-describe="{ row }">
				<span class="text-ink-body">{{ describe(row) }}</span>
			</template>
			<template #cell-team="{ row }">
				<span class="text-ink-body">{{ teamName(row.team) }}</span>
			</template>
			<template #cell-enabled="{ row }">
				<AppCheckbox
					:model-value="Boolean(row.enabled)"
					label="Enabled"
					data-testid="sellos-assignment-rule-enabled"
					@update:model-value="save(row.name, { enabled: $event ? 1 : 0 })"
				/>
			</template>
			<template #cell-actions="{ row }">
				<AppButton
					type="button"
					data-testid="sellos-assignment-rule-remove"
					@click="remove(row)"
				>
					Remove
				</AppButton>
			</template>
		</DataTable>

		<FormDrawer
			:open="adding"
			title="Add a rule"
			text="A rule names a team, and the team's active agents take the leads in turn."
			submit-label="Add rule"
			testid="sellos-assignment-form"
			submit-testid="sellos-assignment-add"
			@close="adding = false"
			@submit="add"
		>
			<FormSection title="Rule">
				<FormField
					v-model="form.rule_name"
					label="Rule name"
					required
					placeholder="For example Pune website leads"
					class="md:col-span-2"
					data-testid="sellos-assignment-name"
				/>
				<FormField
					v-model="form.rule_type"
					type="select"
					label="Assign by"
					:options="typeOptions"
					data-testid="sellos-assignment-type"
				/>
				<FormField
					v-if="form.rule_type === 'Source'"
					v-model="form.source"
					type="select"
					label="Source"
					required
					:options="sourceOptions"
					data-testid="sellos-assignment-source"
				/>
				<FormField
					v-if="form.rule_type === 'Locality'"
					v-model="form.locality"
					label="Locality"
					required
					placeholder="For example Baner"
					data-testid="sellos-assignment-locality"
				/>
				<FormField
					v-model="form.team"
					type="select"
					label="Team"
					required
					:options="teamOptions"
					data-testid="sellos-assignment-team"
				/>
				<FormField
					v-model="form.priority"
					type="number"
					min="0"
					label="Order"
					data-testid="sellos-assignment-priority"
				/>
			</FormSection>
			<p
				v-if="error"
				role="alert"
				class="text-sm text-danger"
				data-testid="sellos-assignment-form-error"
			>
				{{ error }}
			</p>
		</FormDrawer>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import AppCheckbox from "../components/AppCheckbox.vue";
import DataTable from "../components/DataTable.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import KpiStrip from "../components/KpiStrip.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import { crmApi, serverMessage } from "../crm/crmApi";

// The Company Admin's assignment rules and default team (SOS-P1-19). Every change is saved on the
// server and the list read back.
const rules = ref([]);
const teams = ref([]);
const sources = ref([]);
const ruleTypes = ref(["Round robin", "Source", "Locality"]);
const defaultTeam = ref("");
const error = ref("");
const loading = ref(true);
const adding = ref(false);
const kpis = computed(() => [
	{
		label: "Rules",
		value: rules.value.length,
		caption: "tried from the lowest order up",
		icon: "lucide-shuffle",
	},
	{
		label: "Switched on",
		value: rules.value.filter((r) => r.enabled).length,
		caption: "rules in use",
		icon: "lucide-circle-check",
		tone: "success",
	},
	{
		label: "Teams",
		value: teams.value.length,
		caption: "that can take leads",
		icon: "lucide-users-round",
	},
]);
const columns = [
	{ key: "rule_name", label: "Rule", primary: true, sortable: true },
	{ key: "describe", label: "Assigns", sortValue: (r) => describe(r) },
	{ key: "team", label: "Team", sortable: true, sortValue: (r) => teamName(r.team) },
	{ key: "priority", label: "Order", sortable: true, align: "right" },
	{ key: "enabled", label: "Enabled" },
	{ key: "actions", label: "Actions" },
];
const blank = () => ({
	rule_name: "",
	rule_type: "Round robin",
	source: "",
	locality: "",
	team: "",
	priority: 10,
});
const form = reactive(blank());

const choose = (label, items, key = "name", text = key) => [
	{ label, value: "" },
	...items.map((i) => ({ label: i[text], value: i[key] })),
];
const defaultTeamOptions = computed(() =>
	choose("No default team", teams.value, "name", "team_name")
);
const teamOptions = computed(() => choose("Choose a team", teams.value, "name", "team_name"));
const sourceOptions = computed(() => choose("Choose a source", sources.value));
const typeOptions = computed(() => ruleTypes.value.map((t) => ({ label: t, value: t })));

const teamName = (name) => teams.value.find((t) => t.name === name)?.team_name || name;
const describe = (r) =>
	r.rule_type === "Source"
		? `Source ${r.source}`
		: r.rule_type === "Locality"
		? `Locality ${r.locality}`
		: "Every lead";

async function load() {
	try {
		const data = await crmApi.listAssignmentRules();
		rules.value = data.rules;
		teams.value = data.teams;
		sources.value = data.sources;
		ruleTypes.value = data.rule_types;
		defaultTeam.value = data.default_team || "";
	} catch (e) {
		error.value = serverMessage(e, "The rules could not be loaded.");
	} finally {
		loading.value = false;
	}
}

function openAdd() {
	error.value = "";
	adding.value = true;
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

const saveDefault = (value) => {
	defaultTeam.value = value;
	return run(() => crmApi.setDefaultTeam(value), "The default team could not be saved.");
};
const save = (name, values) =>
	run(() => crmApi.saveAssignmentRule(values, name), "The rule could not be saved.");
const remove = (r) =>
	run(() => crmApi.deleteAssignmentRule(r.name), "The rule could not be removed.");

// A frappe-ui select has no native "required", so the form checks what a rule needs before it saves.
async function add() {
	const missing =
		!form.rule_name.trim() ||
		!form.team ||
		(form.rule_type === "Source" && !form.source) ||
		(form.rule_type === "Locality" && !form.locality.trim());
	if (missing) {
		error.value = "Fill in the rule name, what it assigns by, and the team.";
		return;
	}
	await run(
		() => crmApi.saveAssignmentRule({ ...form, priority: Number(form.priority) }),
		"The rule could not be added."
	);
	if (!error.value) {
		Object.assign(form, blank());
		adding.value = false;
	}
}

onMounted(load);
</script>
