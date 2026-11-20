<template>
	<div class="max-w-3xl" data-testid="sellos-assignment-page">
		<PageHeader
			title="Lead assignment"
			text="Every new lead goes to an agent at once. Rules are tried from the lowest order up. A rule names a team, and the team's active agents take the leads in turn. A lead no rule matches goes to the default team."
			icon="lucide-shuffle"
		/>
		<LoadError
			v-if="error"
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

		<ListCard title="Rules" class="mb-ui-md">
			<EmptyState
				v-if="!rules.length"
				title="No rules yet."
				text="Every lead goes to the default team until a rule is added."
				icon="lucide-shuffle"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-assignment-rules">
				<li
					v-for="r in rules"
					:key="r.name"
					data-testid="sellos-assignment-rule"
					:data-name="r.name"
					class="flex flex-wrap items-center gap-ui-md rounded-input border border-line-soft p-ui-sm"
				>
					<span class="font-medium text-ink">{{ r.rule_name }}</span>
					<span class="text-sm text-ink-muted">
						{{ describe(r) }} to {{ teamName(r.team) }}, order {{ r.priority }}
					</span>
					<AppCheckbox
						:model-value="Boolean(r.enabled)"
						label="Enabled"
						data-testid="sellos-assignment-rule-enabled"
						@update:model-value="save(r.name, { enabled: $event ? 1 : 0 })"
					/>
					<AppButton
						type="button"
						data-testid="sellos-assignment-rule-remove"
						@click="remove(r)"
					>
						Remove
					</AppButton>
				</li>
			</ul>
		</ListCard>

		<form data-testid="sellos-assignment-form" @submit.prevent="add">
			<ListCard title="Add a rule">
				<div class="grid gap-ui-md sm:grid-cols-2">
					<FormField
						v-model="form.rule_name"
						label="Rule name"
						required
						placeholder="For example Pune website leads"
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
				</div>
				<div class="mt-ui-md">
					<AppButton variant="primary" type="submit" data-testid="sellos-assignment-add">
						Add rule
					</AppButton>
				</div>
			</ListCard>
		</form>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import AppCheckbox from "../components/AppCheckbox.vue";
import EmptyState from "../components/EmptyState.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import { crmApi, serverMessage } from "../crm/crmApi";

// The Company Admin's assignment rules and default team (SOS-P1-19). Every change is saved on the
// server and the list read back.
const rules = ref([]);
const teams = ref([]);
const sources = ref([]);
const ruleTypes = ref(["Round robin", "Source", "Locality"]);
const defaultTeam = ref("");
const error = ref("");
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
	if (!error.value) Object.assign(form, blank());
}

onMounted(load);
</script>
