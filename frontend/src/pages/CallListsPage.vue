<template>
	<div class="max-w-3xl" data-testid="sellos-calllists-page">
		<h1 class="text-2xl font-semibold text-ink">Call lists</h1>
		<p class="mt-2 text-ink-muted">
			The outcomes an agent picks when logging a call, and the reasons asked for when a lead
			is lost. An outcome or reason that has been used is disabled, never deleted.
		</p>
		<p v-if="error" role="alert" data-testid="sellos-calllists-error" class="mt-3 text-accent">
			{{ error }}
		</p>

		<section class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4">
			<h2 class="font-medium text-ink">Call outcomes</h2>
			<ul class="space-y-2" data-testid="sellos-calllists-outcomes">
				<li
					v-for="o in outcomes"
					:key="o.name"
					data-testid="sellos-calllists-outcome"
					:data-name="o.name"
					class="flex flex-wrap items-center gap-3"
				>
					<span class="w-44 text-ink">{{ o.name }}</span>
					<label class="flex items-center gap-1 text-sm text-ink-muted">
						<input
							type="checkbox"
							:checked="Boolean(o.needs_follow_up)"
							data-testid="sellos-calllists-outcome-followup"
							@change="
								saveOutcome(o, { needs_follow_up: $event.target.checked ? 1 : 0 })
							"
						/>
						Needs a follow up
					</label>
					<select
						:value="o.suggested_stage"
						class="field w-auto"
						aria-label="Suggested stage"
						data-testid="sellos-calllists-outcome-stage"
						@change="saveOutcome(o, { suggested_stage: $event.target.value })"
					>
						<option value="">No suggested stage</option>
						<option v-for="s in stages" :key="s.name" :value="s.name">
							{{ s.name }}
						</option>
					</select>
					<label class="flex items-center gap-1 text-sm text-ink-muted">
						<input
							type="checkbox"
							:checked="Boolean(o.enabled)"
							data-testid="sellos-calllists-outcome-enabled"
							@change="saveOutcome(o, { enabled: $event.target.checked ? 1 : 0 })"
						/>
						Enabled
					</label>
				</li>
			</ul>
			<form
				class="flex flex-wrap gap-2"
				data-testid="sellos-calllists-outcome-form"
				@submit.prevent="addOutcome"
			>
				<input
					v-model="newOutcome.name"
					required
					placeholder="New outcome"
					data-testid="sellos-calllists-new-outcome"
					class="field flex-1"
				/>
				<label class="flex items-center gap-1 text-sm text-ink-muted">
					<input
						v-model="newOutcome.needs_follow_up"
						type="checkbox"
						data-testid="sellos-calllists-new-outcome-followup"
					/>
					Needs a follow up
				</label>
				<select
					v-model="newOutcome.suggested_stage"
					class="field w-auto"
					aria-label="Suggested stage"
					data-testid="sellos-calllists-new-outcome-stage"
				>
					<option value="">No suggested stage</option>
					<option v-for="s in stages" :key="s.name" :value="s.name">{{ s.name }}</option>
				</select>
				<button type="submit" class="btn" data-testid="sellos-calllists-add-outcome">
					Add outcome
				</button>
			</form>
		</section>

		<section class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4">
			<h2 class="font-medium text-ink">Lost reasons</h2>
			<ul class="space-y-2" data-testid="sellos-calllists-reasons">
				<li
					v-for="r in reasons"
					:key="r.name"
					data-testid="sellos-calllists-reason"
					:data-name="r.name"
					class="flex flex-wrap items-center gap-3"
				>
					<span class="w-56 text-ink">{{ r.name }}</span>
					<label class="flex items-center gap-1 text-sm text-ink-muted">
						<input
							type="checkbox"
							:checked="Boolean(r.enabled)"
							data-testid="sellos-calllists-reason-enabled"
							@change="saveReason(r, $event.target.checked ? 1 : 0)"
						/>
						Enabled
					</label>
				</li>
			</ul>
			<form
				class="flex flex-wrap gap-2"
				data-testid="sellos-calllists-reason-form"
				@submit.prevent="addReason"
			>
				<input
					v-model="newReason"
					required
					placeholder="New lost reason"
					data-testid="sellos-calllists-new-reason"
					class="field flex-1"
				/>
				<button type="submit" class="btn" data-testid="sellos-calllists-add-reason">
					Add reason
				</button>
			</form>
		</section>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import { crmApi, serverMessage } from "../crm/crmApi";

// The Company Admin's two lists (SOS-P1-21). Each change saves at once and the lists are read back.
const outcomes = ref([]);
const reasons = ref([]);
const stages = ref([]);
const error = ref("");
const newOutcome = reactive({ name: "", needs_follow_up: false, suggested_stage: "" });
const newReason = ref("");

async function load() {
	try {
		const [o, r, s] = await Promise.all([
			crmApi.listCallOutcomes(1),
			crmApi.listLostReasons(1),
			crmApi.listStages(),
		]);
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

const saveReason = (reason, enabled) =>
	run(() => crmApi.saveLostReason({ enabled }, reason.name), "The reason could not be saved.");

const addOutcome = () =>
	run(async () => {
		await crmApi.saveCallOutcome({
			outcome_name: newOutcome.name,
			needs_follow_up: newOutcome.needs_follow_up ? 1 : 0,
			suggested_stage: newOutcome.suggested_stage,
		});
		Object.assign(newOutcome, { name: "", needs_follow_up: false, suggested_stage: "" });
	}, "The outcome could not be added.");

const addReason = () =>
	run(async () => {
		await crmApi.saveLostReason({ reason_name: newReason.value });
		newReason.value = "";
	}, "The reason could not be added.");

onMounted(load);
</script>
