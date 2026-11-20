<template>
	<div class="max-w-3xl" data-testid="sellos-calllists-page">
		<PageHeader
			title="Call lists"
			text="The outcomes an agent picks when logging a call, and the reasons asked for when a lead is lost. An outcome or reason that has been used is disabled, never deleted."
			icon="lucide-list-checks"
		/>
		<LoadError
			v-if="error"
			class="mb-ui-md"
			data-testid="sellos-calllists-error"
			:message="error"
			@retry="load"
		/>

		<ListCard title="Call outcomes" class="mb-ui-md">
			<ul class="space-y-ui-sm" data-testid="sellos-calllists-outcomes">
				<li
					v-for="o in outcomes"
					:key="o.name"
					data-testid="sellos-calllists-outcome"
					:data-name="o.name"
					class="flex flex-wrap items-center gap-ui-md rounded-input border border-line-soft p-ui-sm"
				>
					<span class="w-44 font-medium text-ink">{{ o.name }}</span>
					<AppCheckbox
						:model-value="Boolean(o.needs_follow_up)"
						label="Needs a follow up"
						data-testid="sellos-calllists-outcome-followup"
						@update:model-value="saveOutcome(o, { needs_follow_up: $event ? 1 : 0 })"
					/>
					<FormField
						:model-value="o.suggested_stage || ''"
						type="select"
						label="Suggested stage"
						:options="stageOptions"
						class="w-56"
						data-testid="sellos-calllists-outcome-stage"
						@update:model-value="saveOutcome(o, { suggested_stage: $event })"
					/>
					<AppCheckbox
						:model-value="Boolean(o.enabled)"
						label="Enabled"
						data-testid="sellos-calllists-outcome-enabled"
						@update:model-value="saveOutcome(o, { enabled: $event ? 1 : 0 })"
					/>
				</li>
			</ul>
			<form
				class="mt-ui-md flex flex-wrap items-end gap-ui-md"
				data-testid="sellos-calllists-outcome-form"
				@submit.prevent="addOutcome"
			>
				<FormField
					v-model="newOutcome.name"
					label="New outcome"
					required
					placeholder="For example Site visit booked"
					class="min-w-48 flex-1"
					data-testid="sellos-calllists-new-outcome"
				/>
				<AppCheckbox
					v-model="newOutcome.needs_follow_up"
					label="Needs a follow up"
					data-testid="sellos-calllists-new-outcome-followup"
				/>
				<FormField
					v-model="newOutcome.suggested_stage"
					type="select"
					label="Suggested stage"
					:options="stageOptions"
					class="w-56"
					data-testid="sellos-calllists-new-outcome-stage"
				/>
				<AppButton type="submit" data-testid="sellos-calllists-add-outcome">
					Add outcome
				</AppButton>
			</form>
		</ListCard>

		<ListCard title="Lost reasons" class="mb-ui-md">
			<ul class="space-y-ui-sm" data-testid="sellos-calllists-reasons">
				<li
					v-for="r in reasons"
					:key="r.name"
					data-testid="sellos-calllists-reason"
					:data-name="r.name"
					class="flex flex-wrap items-center gap-ui-md rounded-input border border-line-soft p-ui-sm"
				>
					<span class="w-56 font-medium text-ink">{{ r.name }}</span>
					<AppCheckbox
						:model-value="Boolean(r.enabled)"
						label="Enabled"
						data-testid="sellos-calllists-reason-enabled"
						@update:model-value="saveReason(r, $event ? 1 : 0)"
					/>
				</li>
			</ul>
			<form
				class="mt-ui-md flex flex-wrap items-end gap-ui-md"
				data-testid="sellos-calllists-reason-form"
				@submit.prevent="addReason"
			>
				<FormField
					v-model="newReason"
					label="New lost reason"
					required
					placeholder="For example Budget too low"
					class="min-w-48 flex-1"
					data-testid="sellos-calllists-new-reason"
				/>
				<AppButton type="submit" data-testid="sellos-calllists-add-reason">
					Add reason
				</AppButton>
			</form>
		</ListCard>

		<ListCard title="Untouched leads">
			<p class="mb-ui-md text-sm text-ink-muted">
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
		</ListCard>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import AppCheckbox from "../components/AppCheckbox.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
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

const saveReason = (reason, enabled) =>
	run(() => crmApi.saveLostReason({ enabled }, reason.name), "The reason could not be saved.");

// A name is needed: frappe-ui fields have no native "required", so the form checks it.
async function addOutcome() {
	if (!newOutcome.name.trim()) return;
	await run(async () => {
		await crmApi.saveCallOutcome({
			outcome_name: newOutcome.name,
			needs_follow_up: newOutcome.needs_follow_up ? 1 : 0,
			suggested_stage: newOutcome.suggested_stage,
		});
		Object.assign(newOutcome, { name: "", needs_follow_up: false, suggested_stage: "" });
	}, "The outcome could not be added.");
}

async function addReason() {
	if (!newReason.value.trim()) return;
	await run(async () => {
		await crmApi.saveLostReason({ reason_name: newReason.value });
		newReason.value = "";
	}, "The reason could not be added.");
}

onMounted(load);
</script>
