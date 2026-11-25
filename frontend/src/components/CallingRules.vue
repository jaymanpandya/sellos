<template>
	<!-- Two settings cards, each with its own Save, inside the Telephony page. -->
	<div v-if="loaded" class="mt-4 space-y-4" data-testid="sellos-calling-rules">
		<form data-testid="sellos-calling-hours-form" @submit.prevent="saveHours">
			<SectionCard
				title="Calling hours"
				help="Calls to Indian numbers are placed only inside these hours, in India time. A call outside them is refused and the message shows the hours."
			>
				<FieldGrid>
					<FormField
						v-model="hours.enabled"
						type="checkbox"
						label="Limit calls to these hours"
						class="md:col-span-2"
						data-testid="sellos-calling-hours-enabled"
					/>
					<FormField
						v-model="hours.start"
						type="time"
						label="Calls may start at"
						data-testid="sellos-calling-hours-start"
					/>
					<FormField
						v-model="hours.end"
						type="time"
						label="Calls must end by"
						data-testid="sellos-calling-hours-end"
					/>
					<div class="flex flex-wrap gap-x-4 md:col-span-2">
						<FormField
							v-for="day in days"
							:key="day"
							:model-value="hours.days.includes(day)"
							type="checkbox"
							:label="day"
							:data-testid="`sellos-calling-day-${day}`"
							@update:model-value="toggleDay(day, $event)"
						/>
					</div>
				</FieldGrid>
				<div class="mt-4 space-y-2">
					<p
						v-if="hoursError"
						role="alert"
						class="ui-text-error"
						data-testid="sellos-calling-hours-error"
					>
						{{ hoursError }}
					</p>
					<p
						v-if="hoursSaved"
						class="ui-text-small"
						data-testid="sellos-calling-hours-saved"
					>
						Saved. {{ hoursText }}
					</p>
				</div>
				<template #footer>
					<AppButton
						type="submit"
						variant="primary"
						data-testid="sellos-calling-hours-save"
					>
						Save calling hours
					</AppButton>
				</template>
			</SectionCard>
		</form>

		<form data-testid="sellos-dnd-form" @submit.prevent="importList">
			<SectionCard
				title="Do not call list"
				help="Paste the numbers, one on each line or as a CSV. A lead with a listed number is marked Registered DND with an amber warning. The warning never stops a call."
			>
				<FieldGrid>
					<FormField
						v-model="listText"
						type="textarea"
						label="Numbers"
						class="md:col-span-2"
						data-testid="sellos-dnd-text"
					/>
				</FieldGrid>
				<div class="mt-4 space-y-2">
					<p
						v-if="listError"
						role="alert"
						class="ui-text-error"
						data-testid="sellos-dnd-error"
					>
						{{ listError }}
					</p>
					<p v-if="result" class="ui-text-small" data-testid="sellos-dnd-result">
						{{ result.added }} added, {{ result.already_listed }} already listed,
						{{ result.skipped }} skipped. {{ result.leads_flagged }} leads marked
						Registered DND.
					</p>
					<p class="ui-text-muted" data-testid="sellos-dnd-total">
						Numbers on the list: {{ total }}
					</p>
				</div>
				<template #footer>
					<AppButton type="submit" variant="primary" data-testid="sellos-dnd-import">
						Import list
					</AppButton>
				</template>
			</SectionCard>
		</form>
	</div>
</template>

<script setup>
// Calling hours and the do not call list (SOS-P2-10): both are Company Admin settings, and neither can
// block a call by consent. Built from the shared components (docs/UI_STYLE.md).
import { onMounted, reactive, ref } from "vue";

import { serverMessage } from "../crm/crmApi";
import { callingRulesApi } from "../telephony/telephonyApi";
import AppButton from "./AppButton.vue";
import FieldGrid from "./FieldGrid.vue";
import FormField from "./FormField.vue";
import SectionCard from "./SectionCard.vue";

const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const hours = reactive({ enabled: false, start: "09:00", end: "21:00", days: [] });
const hoursError = ref("");
const hoursSaved = ref(false);
const hoursText = ref("");
const listText = ref("");
const listError = ref("");
const result = ref(null);
const total = ref(0);
const loaded = ref(false); // the forms open only once the saved values are in, so a late load never undoes a click

function apply(state) {
	hours.enabled = !!state.enabled;
	hours.start = state.start;
	hours.end = state.end;
	hours.days = [...state.days];
	hoursText.value = state.text || "";
}

function toggleDay(day, on) {
	hours.days = on ? [...new Set([...hours.days, day])] : hours.days.filter((d) => d !== day);
}

async function saveHours() {
	hoursError.value = "";
	hoursSaved.value = false;
	try {
		apply(await callingRulesApi.saveHours(hours));
		hoursSaved.value = true;
	} catch (e) {
		hoursError.value = serverMessage(e, "The calling hours could not be saved.");
	}
}

async function importList() {
	listError.value = "";
	result.value = null;
	try {
		const done = await callingRulesApi.importList(listText.value);
		result.value = done;
		total.value = done.total;
		listText.value = "";
	} catch (e) {
		listError.value = serverMessage(e, "The list could not be imported.");
	}
}

onMounted(async () => {
	try {
		apply(await callingRulesApi.getHours());
		total.value = (await callingRulesApi.summary()).total;
	} catch (e) {
		hoursError.value = serverMessage(e, "The calling rules could not be loaded.");
	} finally {
		loaded.value = true;
	}
});
</script>
