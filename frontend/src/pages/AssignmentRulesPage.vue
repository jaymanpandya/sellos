<template>
	<div class="max-w-3xl" data-testid="sellos-assignment-page">
		<h1 class="ui-page-title">Lead assignment</h1>
		<p class="mt-2 text-ink-muted">
			Every new lead goes to an agent at once. Rules are tried from the lowest order up. A
			rule names a team, and the team's active agents take the leads in turn. A lead no rule
			matches goes to the default team.
		</p>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-assignment-error"
			class="mt-3 text-accent"
		>
			{{ error }}
		</p>

		<section class="mt-4 space-y-2 rounded-input border border-line bg-surface p-4">
			<h2 class="font-medium text-ink">Default team</h2>
			<select
				v-model="defaultTeam"
				aria-label="Default team"
				data-testid="sellos-assignment-default"
				class="field"
				@change="saveDefault"
			>
				<option value="">No default team</option>
				<option v-for="t in teams" :key="t.name" :value="t.name">{{ t.team_name }}</option>
			</select>
		</section>

		<ul class="mt-4 space-y-2" data-testid="sellos-assignment-rules">
			<li
				v-for="r in rules"
				:key="r.name"
				data-testid="sellos-assignment-rule"
				:data-name="r.name"
				class="flex flex-wrap items-center gap-3 rounded-input border border-line bg-surface p-3"
			>
				<span class="font-medium text-ink">{{ r.rule_name }}</span>
				<span class="text-sm text-ink-muted">
					{{ describe(r) }} to {{ teamName(r.team) }}, order {{ r.priority }}
				</span>
				<label class="flex items-center gap-1 text-sm text-ink-muted">
					<input
						type="checkbox"
						:checked="Boolean(r.enabled)"
						data-testid="sellos-assignment-rule-enabled"
						@change="save(r.name, { enabled: $event.target.checked ? 1 : 0 })"
					/>
					Enabled
				</label>
				<button
					type="button"
					class="btn"
					data-testid="sellos-assignment-rule-remove"
					@click="remove(r)"
				>
					Remove
				</button>
			</li>
		</ul>

		<form
			class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4"
			data-testid="sellos-assignment-form"
			@submit.prevent="add"
		>
			<h2 class="font-medium text-ink">Add a rule</h2>
			<input
				v-model="form.rule_name"
				required
				placeholder="Rule name"
				aria-label="Rule name"
				data-testid="sellos-assignment-name"
				class="field"
			/>
			<select
				v-model="form.rule_type"
				aria-label="Assign by"
				data-testid="sellos-assignment-type"
				class="field"
			>
				<option v-for="t in ruleTypes" :key="t" :value="t">{{ t }}</option>
			</select>
			<select
				v-if="form.rule_type === 'Source'"
				v-model="form.source"
				required
				aria-label="Source"
				data-testid="sellos-assignment-source"
				class="field"
			>
				<option value="" disabled>Choose a source</option>
				<option v-for="s in sources" :key="s.name" :value="s.name">{{ s.name }}</option>
			</select>
			<input
				v-if="form.rule_type === 'Locality'"
				v-model="form.locality"
				required
				placeholder="Locality"
				aria-label="Locality"
				data-testid="sellos-assignment-locality"
				class="field"
			/>
			<select
				v-model="form.team"
				required
				aria-label="Team"
				data-testid="sellos-assignment-team"
				class="field"
			>
				<option value="" disabled>Choose a team</option>
				<option v-for="t in teams" :key="t.name" :value="t.name">{{ t.team_name }}</option>
			</select>
			<input
				v-model.number="form.priority"
				type="number"
				min="0"
				aria-label="Order"
				data-testid="sellos-assignment-priority"
				class="field"
			/>
			<button type="submit" class="btn" data-testid="sellos-assignment-add">Add rule</button>
		</form>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

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

const saveDefault = () =>
	run(() => crmApi.setDefaultTeam(defaultTeam.value), "The default team could not be saved.");
const save = (name, values) =>
	run(() => crmApi.saveAssignmentRule(values, name), "The rule could not be saved.");
const remove = (r) =>
	run(() => crmApi.deleteAssignmentRule(r.name), "The rule could not be removed.");

async function add() {
	await run(() => crmApi.saveAssignmentRule({ ...form }), "The rule could not be added.");
	if (!error.value) Object.assign(form, blank());
}

onMounted(load);
</script>
