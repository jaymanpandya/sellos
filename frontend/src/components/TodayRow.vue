<template>
	<li
		class="rounded-input border border-line-soft p-ui-md"
		data-testid="sellos-today-row"
		:data-lead="row.lead"
		:data-section="section"
	>
		<div class="flex flex-wrap items-center justify-between gap-ui-sm">
			<div class="flex min-w-0 flex-wrap items-center gap-ui-sm">
				<router-link
					:to="`/crm/leads/${row.lead}`"
					class="ui-link font-medium"
					data-testid="sellos-today-lead"
					>{{ row.lead_title }}</router-link
				>
				<span class="text-sm text-ink-muted" data-testid="sellos-today-detail">{{
					detail
				}}</span>
				<StatusBadge
					v-if="row.state === 'overdue'"
					tone="danger"
					label="Overdue"
					data-testid="sellos-today-overdue"
				/>
				<StatusBadge
					v-if="row.consent_warning"
					:tone="row.consent_warning === 'red' ? 'danger' : 'warning'"
					:label="row.consent_status"
					data-testid="sellos-today-consent"
					:data-level="row.consent_warning"
					:title="row.consent_message"
				/>
			</div>
			<div class="flex flex-wrap gap-ui-sm">
				<AppButton
					type="button"
					data-testid="sellos-today-call"
					:aria-expanded="showNumber"
					@click="showNumber = !showNumber"
				>
					Call
				</AppButton>
				<AppButton
					type="button"
					data-testid="sellos-today-log"
					:aria-expanded="logging"
					@click="logging = !logging"
				>
					Log
				</AppButton>
			</div>
		</div>

		<p v-if="showNumber" class="mt-ui-sm text-sm text-ink" data-testid="sellos-today-number">
			<template v-if="row.phone">
				<a v-if="fullNumbers" :href="`tel:${row.phone}`" class="ui-link">{{
					row.phone
				}}</a>
				<span v-else>{{ row.phone }}</span>
				<span v-if="row.overseas_phone"> · {{ row.overseas_phone }}</span>
			</template>
			<template v-else>No phone</template>
		</p>

		<form
			v-if="logging"
			class="mt-ui-sm space-y-ui-sm"
			data-testid="sellos-today-log-form"
			@submit.prevent="save"
		>
			<div class="grid grid-cols-1 gap-ui-md sm:grid-cols-2">
				<FormField
					v-model="form.outcome"
					type="select"
					label="Outcome"
					required
					:options="outcomeOptions"
					data-testid="sellos-today-log-outcome"
				/>
				<FormField
					v-model="form.notes"
					label="Notes"
					data-testid="sellos-today-log-notes"
				/>
			</div>
			<FormField
				v-if="chosen?.needs_follow_up"
				v-model="form.followUp"
				required
				type="datetime-local"
				label="Follow up on"
				data-testid="sellos-today-log-follow-up"
			/>
			<p
				v-if="error"
				role="alert"
				data-testid="sellos-today-log-error"
				class="text-sm text-tone-danger"
			>
				{{ error }}
			</p>
			<AppButton type="submit" variant="primary" data-testid="sellos-today-log-save">
				Save
			</AppButton>
		</form>
		<slot />
	</li>
</template>

<script setup>
import { computed, reactive, ref } from "vue";

import { crmApi, serverMessage } from "../crm/crmApi";
import AppButton from "./AppButton.vue";
import FormField from "./FormField.vue";
import StatusBadge from "./StatusBadge.vue";

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
const outcomeOptions = computed(() => [
	{ label: "Choose an outcome", value: "" },
	...props.outcomes.map((o) => ({ label: o.name, value: o.name })),
]);
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
