<template>
	<li
		class="rounded-input border border-line p-3"
		data-testid="sellos-today-row"
		:data-lead="row.lead"
		:data-section="section"
	>
		<div class="flex flex-wrap items-center justify-between gap-2">
			<div class="min-w-0">
				<router-link
					:to="`/crm/leads/${row.lead}`"
					class="font-medium text-ink underline"
					data-testid="sellos-today-lead"
					>{{ row.lead_title }}</router-link
				>
				<span class="ml-2 text-sm text-ink-muted" data-testid="sellos-today-detail">{{
					detail
				}}</span>
				<span
					v-if="row.state === 'overdue'"
					data-testid="sellos-today-overdue"
					class="ml-2 rounded-input border border-accent px-2 py-1 text-xs text-accent"
					>Overdue</span
				>
				<span
					v-if="row.consent_warning"
					data-testid="sellos-today-consent"
					:data-level="row.consent_warning"
					:title="row.consent_message"
					class="ml-2 rounded-input border px-2 py-1 text-xs"
					:class="
						row.consent_warning === 'red'
							? 'border-accent text-accent'
							: 'border-line text-ink-muted'
					"
					>{{ row.consent_status }}</span
				>
			</div>
			<div class="flex flex-wrap gap-2">
				<button
					type="button"
					class="btn"
					data-testid="sellos-today-call"
					:aria-expanded="showNumber"
					@click="showNumber = !showNumber"
				>
					Call
				</button>
				<button
					type="button"
					class="btn"
					data-testid="sellos-today-log"
					:aria-expanded="logging"
					@click="logging = !logging"
				>
					Log
				</button>
			</div>
		</div>

		<p v-if="showNumber" class="mt-2 text-sm text-ink" data-testid="sellos-today-number">
			<template v-if="row.phone">
				<a v-if="fullNumbers" :href="`tel:${row.phone}`" class="underline">{{
					row.phone
				}}</a>
				<span v-else>{{ row.phone }}</span>
				<span v-if="row.overseas_phone"> · {{ row.overseas_phone }}</span>
			</template>
			<template v-else>No phone</template>
		</p>

		<form
			v-if="logging"
			class="mt-2 space-y-2"
			data-testid="sellos-today-log-form"
			@submit.prevent="save"
		>
			<div class="flex flex-wrap gap-2">
				<select
					v-model="form.outcome"
					required
					aria-label="Outcome"
					data-testid="sellos-today-log-outcome"
					class="field w-auto"
				>
					<option value="">Outcome</option>
					<option v-for="o in outcomes" :key="o.name" :value="o.name">
						{{ o.name }}
					</option>
				</select>
				<input
					v-model="form.notes"
					placeholder="Notes"
					aria-label="Notes"
					data-testid="sellos-today-log-notes"
					class="field flex-1"
				/>
			</div>
			<label v-if="chosen?.needs_follow_up" class="block text-sm text-ink-muted">
				Follow up on
				<input
					v-model="form.followUp"
					required
					type="datetime-local"
					data-testid="sellos-today-log-follow-up"
					class="field w-auto"
				/>
			</label>
			<p
				v-if="error"
				role="alert"
				data-testid="sellos-today-log-error"
				class="text-sm text-accent"
			>
				{{ error }}
			</p>
			<button type="submit" class="btn" data-testid="sellos-today-log-save">Save</button>
		</form>
		<slot />
	</li>
</template>

<script setup>
import { computed, reactive, ref } from "vue";

import { crmApi, serverMessage } from "../crm/crmApi";

// One row of the Today screen (SOS-P1-26). Call shows the number the person's role may see (a Company
// Admin's is a link to dial, an Agent's and a Sales Manager's is masked). Log records a call in place:
// on a follow up it marks the follow up done, on any other row it logs a call on the lead. Consent is
// shown as a warning and never stops either.
const props = defineProps({
	row: { type: Object, required: true },
	section: { type: String, required: true },
	outcomes: { type: Array, default: () => [] },
	fullNumbers: { type: Boolean, default: false },
});
const emit = defineEmits(["logged"]);

const showNumber = ref(false);
const logging = ref(false);
const error = ref("");
const form = reactive({ outcome: "", notes: "", followUp: "" });
const chosen = computed(() => props.outcomes.find((o) => o.name === form.outcome));

const detail = computed(() => {
	const row = props.row;
	const who = row.agent_name ? `, ${row.agent_name}` : "";
	if (props.section === "follow_ups") {
		const when = row.due_at ? String(row.due_at).slice(11, 16) : "today";
		return `${row.title} at ${when}${who}`;
	}
	if (props.section === "new_leads") return `New lead${who}`;
	return `${row.project_name} at ${String(row.visit_datetime).slice(11, 16)}${who}`;
});

async function save() {
	error.value = "";
	const values = {
		outcome: form.outcome,
		notes: form.notes,
		follow_up_at: chosen.value?.needs_follow_up ? form.followUp : null,
	};
	try {
		if (props.section === "follow_ups") await crmApi.completeFollowUp(props.row.name, values);
		else await crmApi.logCall(props.row.lead, values);
		Object.assign(form, { outcome: "", notes: "", followUp: "" });
		logging.value = false;
		emit("logged");
	} catch (e) {
		error.value = serverMessage(e, "The call could not be logged.");
	}
}
</script>
