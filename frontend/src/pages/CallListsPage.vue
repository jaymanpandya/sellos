<template>
	<PageTemplate shape="list" data-testid="sellos-calllists-page">
		<template #header>
			<PageHeader
				title="Call lists"
				text="The outcomes an agent picks when logging a call, and the reasons asked for when a lead is lost. An outcome or reason that has been used is disabled, never deleted."
				icon="lucide-list-checks"
			>
				<AppButton
					type="button"
					data-testid="sellos-calllists-new-reason-open"
					@click="openReason"
				>
					<template #prefix
						><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
					/></template>
					Add lost reason
				</AppButton>
				<AppButton
					type="button"
					data-testid="sellos-calllists-new-outcome-open"
					@click="openOutcome"
				>
					<template #prefix
						><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
					/></template>
					Add outcome
				</AppButton>
			</PageHeader>
		</template>

		<template #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-calllists-stats" />
		</template>

		<LoadError
			v-if="error"
			class="mb-ui-md"
			data-testid="sellos-calllists-error"
			:message="error"
			@retry="load"
		/>

		<DataTable
			class="mb-ui-md"
			title="Call outcomes"
			caption="Call outcomes"
			:columns="outcomeColumns"
			:rows="outcomes"
			:actions="outcomeActions"
			:page-size="50"
			:row-name="(o) => o.name"
			empty-title="No call outcomes yet."
			empty-text="Add the first outcome an agent can pick."
			testid="sellos-calllists-outcomes"
			row-testid="sellos-calllists-outcome"
		>
			<template #cell-name="{ row }">
				<NameCell :name="row.name" />
			</template>
			<template #cell-needs_follow_up="{ row }">
				<StatusBadge
					:tone="row.needs_follow_up ? 'info' : 'neutral'"
					:label="row.needs_follow_up ? 'Follow up' : 'No follow up'"
					data-testid="sellos-calllists-outcome-followup"
				/>
			</template>
			<template #cell-suggested_stage="{ row }">
				<CellText
					:value="row.suggested_stage"
					data-testid="sellos-calllists-outcome-stage"
				/>
			</template>
			<template #cell-enabled="{ row }">
				<StatusBadge
					:tone="row.enabled ? 'success' : 'neutral'"
					:label="row.enabled ? 'Enabled' : 'Disabled'"
					data-testid="sellos-calllists-outcome-enabled"
				/>
			</template>
		</DataTable>

		<DataTable
			class="mb-ui-md"
			title="Lost reasons"
			caption="Lost reasons"
			:columns="reasonColumns"
			:rows="reasons"
			:actions="reasonActions"
			:page-size="50"
			:row-name="(r) => r.name"
			empty-title="No lost reasons yet."
			empty-text="Add the first reason asked for when a lead is lost."
			testid="sellos-calllists-reasons"
			row-testid="sellos-calllists-reason"
		>
			<template #cell-name="{ row }">
				<NameCell :name="row.name" />
			</template>
			<template #cell-enabled="{ row }">
				<StatusBadge
					:tone="row.enabled ? 'success' : 'neutral'"
					:label="row.enabled ? 'Enabled' : 'Disabled'"
					data-testid="sellos-calllists-reason-enabled"
				/>
			</template>
		</DataTable>

		<SectionCard title="Untouched leads">
			<p class="mb-ui-md ui-text-muted">
				A lead in an open stage with no open follow up is flagged untouched after this many
				days.
			</p>
			<form
				class="flex flex-wrap items-end gap-ui-md"
				data-testid="sellos-calllists-untouched-form"
				@submit.prevent="saveUntouched"
			>
				<FormField
					v-model="untouchedDays"
					required
					type="number"
					min="1"
					max="365"
					label="Days before a lead is untouched"
					class="w-64"
					data-testid="sellos-calllists-untouched-days"
				/>
				<AppButton
					variant="primary"
					type="submit"
					data-testid="sellos-calllists-untouched-save"
				>
					Save days
				</AppButton>
				<StatusBadge
					v-if="untouchedSaved"
					tone="success"
					label="Saved."
					role="status"
					data-testid="sellos-calllists-untouched-saved"
				/>
			</form>
		</SectionCard>

		<!-- Editing an outcome: the follow up, the suggested stage and whether it is enabled. -->
		<FormDrawer
			:open="Boolean(editing)"
			:title="editing ? `Edit ${editing.name}` : 'Edit outcome'"
			text="An outcome that has been used is disabled, never deleted."
			submit-label="Save outcome"
			testid="sellos-calllists-edit-form"
			submit-testid="sellos-calllists-edit-save"
			@close="editing = null"
			@submit="saveEdit"
		>
			<FormSection title="Outcome">
				<FormField
					v-model="editForm.suggested_stage"
					type="select"
					label="Suggested stage"
					:options="stageOptions"
					data-testid="sellos-calllists-edit-stage"
				/>
				<AppCheckbox
					v-model="editForm.needs_follow_up"
					label="Needs a follow up"
					data-testid="sellos-calllists-edit-followup"
				/>
				<AppCheckbox
					v-model="editForm.enabled"
					label="Enabled"
					data-testid="sellos-calllists-edit-enabled"
				/>
			</FormSection>
		</FormDrawer>

		<!-- The two add forms are drawers: nothing is an open form under a list. -->
		<FormDrawer
			:open="outcomeOpen"
			title="Add a call outcome"
			text="An agent picks it when logging a call."
			submit-label="Add outcome"
			testid="sellos-calllists-outcome-form"
			submit-testid="sellos-calllists-add-outcome"
			@close="outcomeOpen = false"
			@submit="addOutcome"
		>
			<FormSection title="Outcome">
				<FormField
					v-model="newOutcome.name"
					label="New outcome"
					required
					placeholder="For example Site visit booked"
					class="md:col-span-2"
					data-testid="sellos-calllists-new-outcome"
				/>
				<FormField
					v-model="newOutcome.suggested_stage"
					type="select"
					label="Suggested stage"
					:options="stageOptions"
					data-testid="sellos-calllists-new-outcome-stage"
				/>
				<AppCheckbox
					v-model="newOutcome.needs_follow_up"
					label="Needs a follow up"
					data-testid="sellos-calllists-new-outcome-followup"
				/>
			</FormSection>
			<p v-if="formError" role="alert" class="ui-text-error">{{ formError }}</p>
		</FormDrawer>
		<FormDrawer
			:open="reasonOpen"
			title="Add a lost reason"
			text="Asked for when a lead is lost."
			submit-label="Add reason"
			testid="sellos-calllists-reason-form"
			submit-testid="sellos-calllists-add-reason"
			@close="reasonOpen = false"
			@submit="addReason"
		>
			<FormSection title="Reason">
				<FormField
					v-model="newReason"
					label="New lost reason"
					required
					placeholder="For example Budget too low"
					class="md:col-span-2"
					data-testid="sellos-calllists-new-reason"
				/>
			</FormSection>
			<p v-if="formError" role="alert" class="ui-text-error">{{ formError }}</p>
		</FormDrawer>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import AppCheckbox from "../components/AppCheckbox.vue";
import CellText from "../components/CellText.vue";
import DataTable from "../components/DataTable.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import NameCell from "../components/NameCell.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import SectionCard from "../components/SectionCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { crmApi, serverMessage } from "../crm/crmApi";

// The Company Admin's two lists (SOS-P1-21). Each change saves at once and the lists are read back.
const outcomes = ref([]);
const reasons = ref([]);
const stages = ref([]);
const error = ref("");
const newOutcome = reactive({ name: "", needs_follow_up: false, suggested_stage: "" });
const newReason = ref("");
const untouchedDays = ref(3);
const untouchedSaved = ref(false);
const outcomeOpen = ref(false);
const reasonOpen = ref(false);
const formError = ref("");

const editing = ref(null);
const editForm = reactive({ needs_follow_up: false, suggested_stage: "", enabled: true });

const outcomeColumns = [
	{ key: "name", label: "Outcome", primary: true },
	{ key: "needs_follow_up", label: "Needs a follow up" },
	{ key: "suggested_stage", label: "Suggested stage" },
	{ key: "enabled", label: "Enabled" },
];
const reasonColumns = [
	{ key: "name", label: "Lost reason", primary: true },
	{ key: "enabled", label: "Enabled" },
];
const kpis = computed(() => [
	{
		label: "Call outcomes",
		value: outcomes.value.length,
		caption: `${outcomes.value.filter((o) => o.enabled).length} enabled`,
		icon: "lucide-phone-call",
	},
	{
		label: "Lost reasons",
		value: reasons.value.length,
		caption: `${reasons.value.filter((r) => r.enabled).length} enabled`,
		icon: "lucide-circle-x",
	},
	{
		label: "Untouched after",
		value: `${untouchedDays.value} days`,
		caption: "With no open follow up",
		icon: "lucide-clock",
		tone: "warning",
	},
]);

function openOutcome() {
	formError.value = "";
	outcomeOpen.value = true;
}
function openReason() {
	formError.value = "";
	reasonOpen.value = true;
}
const stageOptions = computed(() => [
	{ label: "No suggested stage", value: "" },
	...stages.value.map((s) => ({ label: s.name, value: s.name })),
]);

async function load() {
	try {
		const [o, r, s, f] = await Promise.all([
			crmApi.listCallOutcomes(1),
			crmApi.listLostReasons(1),
			crmApi.listStages(),
			crmApi.getFollowUpSettings(),
		]);
		untouchedDays.value = f.untouched_days;
		outcomes.value = o.outcomes;
		reasons.value = r.lost_reasons;
		stages.value = s;
	} catch (e) {
		error.value = serverMessage(e, "The lists could not be loaded.");
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

const saveOutcome = (outcome, values) =>
	run(() => crmApi.saveCallOutcome(values, outcome.name), "The outcome could not be saved.");

// The number of days after which a lead with no open follow up is untouched (SOS-P1-22).
async function saveUntouched() {
	untouchedSaved.value = false;
	error.value = "";
	try {
		const saved = await crmApi.saveFollowUpSettings(Number(untouchedDays.value));
		untouchedDays.value = saved.untouched_days;
		untouchedSaved.value = true;
	} catch (e) {
		error.value = serverMessage(e, "The number of days could not be saved.");
	}
}

// Every row action is in the row menu (docs/DESIGN_SYSTEM.md, "Lists", rule c).
const outcomeActions = (row) => [
	{
		label: "Edit outcome",
		onClick: () => {
			Object.assign(editForm, {
				needs_follow_up: Boolean(row.needs_follow_up),
				suggested_stage: row.suggested_stage || "",
				enabled: Boolean(row.enabled),
			});
			editing.value = row;
		},
	},
	row.enabled
		? { label: "Disable", onClick: () => saveOutcome(row, { enabled: 0 }) }
		: { label: "Enable", onClick: () => saveOutcome(row, { enabled: 1 }) },
];
const reasonActions = (row) => [
	row.enabled
		? { label: "Disable", onClick: () => saveReason(row, 0) }
		: { label: "Enable", onClick: () => saveReason(row, 1) },
];
async function saveEdit() {
	const outcome = editing.value;
	if (!outcome) return;
	editing.value = null;
	await saveOutcome(outcome, {
		needs_follow_up: editForm.needs_follow_up ? 1 : 0,
		suggested_stage: editForm.suggested_stage,
		enabled: editForm.enabled ? 1 : 0,
	});
}

const saveReason = (reason, enabled) =>
	run(() => crmApi.saveLostReason({ enabled }, reason.name), "The reason could not be saved.");

// A name is needed: frappe-ui fields have no native "required", so the form checks it. The drawer closes
// when the list is saved, and keeps its own error when it is not.
async function addOutcome() {
	if (!newOutcome.name.trim()) return;
	formError.value = "";
	try {
		await crmApi.saveCallOutcome({
			outcome_name: newOutcome.name,
			needs_follow_up: newOutcome.needs_follow_up ? 1 : 0,
			suggested_stage: newOutcome.suggested_stage,
		});
		Object.assign(newOutcome, { name: "", needs_follow_up: false, suggested_stage: "" });
		outcomeOpen.value = false;
	} catch (e) {
		formError.value = serverMessage(e, "The outcome could not be added.");
		return;
	}
	await load();
}

async function addReason() {
	if (!newReason.value.trim()) return;
	formError.value = "";
	try {
		await crmApi.saveLostReason({ reason_name: newReason.value });
		newReason.value = "";
		reasonOpen.value = false;
	} catch (e) {
		formError.value = serverMessage(e, "The reason could not be added.");
		return;
	}
	await load();
}

onMounted(load);
</script>
