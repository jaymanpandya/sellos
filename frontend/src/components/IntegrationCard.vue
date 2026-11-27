<template>
	<SectionCard
		:title="card.title"
		:help="card.help"
		:data-testid="`sellos-integration-${card.provider}`"
	>
		<template #actions>
			<StatusBadge
				:tone="TONE[card.status] || 'neutral'"
				:label="card.status"
				:data-testid="`sellos-integration-${card.provider}-status`"
			/>
		</template>
		<form :data-testid="`sellos-integration-${card.provider}-form`" @submit.prevent="save">
			<FieldGrid>
				<FormField
					v-for="field in card.fields"
					:key="field.key"
					v-model="form[field.key]"
					:type="inputType(field)"
					:label="field.label"
					:hint="field.saved"
					:placeholder="field.secret && field.saved ? 'Type to replace it' : ''"
					:autocomplete="field.secret ? 'off' : undefined"
					:data-testid="`sellos-integration-${card.provider}-${field.key}`"
				/>
			</FieldGrid>
			<dl v-if="card.webhook_url" class="mt-4">
				<FieldGrid>
					<ReadField
						:label="
							card.provider === 'whatsapp'
								? 'Webhook URL to paste into Meta'
								: 'Webhook address'
						"
						:value="card.webhook_url"
						:data-testid="`sellos-integration-${card.provider}-webhook`"
					/>
					<ReadField
						v-if="card.webhook_header"
						label="Webhook header name"
						:value="card.webhook_header"
					/>
				</FieldGrid>
			</dl>
			<div class="mt-4 space-y-2">
				<p
					v-if="card.status === 'Failed' && card.reason"
					role="alert"
					class="ui-text-error"
					:data-testid="`sellos-integration-${card.provider}-reason`"
				>
					{{ card.reason }}
				</p>
				<p
					v-if="error"
					role="alert"
					class="ui-text-error"
					:data-testid="`sellos-integration-${card.provider}-error`"
				>
					{{ error }}
				</p>
				<p
					v-if="notice"
					role="status"
					class="ui-text-small"
					:data-testid="`sellos-integration-${card.provider}-notice`"
				>
					{{ notice }}
				</p>
			</div>
			<div
				class="mt-4 flex flex-wrap items-center justify-end gap-2 border-t border-line-soft pt-4"
			>
				<AppButton
					type="button"
					:disabled="busy"
					:data-testid="`sellos-integration-${card.provider}-test`"
					@click="test"
				>
					Test connection
				</AppButton>
				<AppButton
					type="submit"
					variant="primary"
					:disabled="busy"
					:data-testid="`sellos-integration-${card.provider}-save`"
				>
					Save
				</AppButton>
			</div>
		</form>
	</SectionCard>
</template>

<script setup>
import { reactive, ref } from "vue";

import AppButton from "./AppButton.vue";
import FieldGrid from "./FieldGrid.vue";
import FormField from "./FormField.vue";
import ReadField from "./ReadField.vue";
import SectionCard from "./SectionCard.vue";
import StatusBadge from "./StatusBadge.vue";
import { integrationsApi } from "../company/integrationsApi";
import { serverMessage } from "../crm/crmApi";

// One provider's card on the Integrations screen (SOS-INT-1): its fields, a status pill (Not set, Not tested, Connected
// or Failed with the provider's plain reason), Save and Test connection. A saved secret is never sent to the browser:
// the field is empty and its hint reads "Saved, ending xxxx"; typing in it replaces the secret, leaving it empty keeps it.
const props = defineProps({ card: { type: Object, required: true } });
const emit = defineEmits(["update"]);

const TONE = {
	Connected: "success",
	Failed: "danger",
	"Not tested": "warning",
	"Not set": "neutral",
};
const KIND_TYPE = {
	email: "email",
	port: "number",
	digits: "text",
	url: "text",
	host: "text",
	text: "text",
};

const form = reactive({});
const error = ref("");
const notice = ref("");
const busy = ref(false);

function fill(card) {
	for (const field of card.fields) form[field.key] = field.secret ? "" : field.value;
}
fill(props.card);

const inputType = (field) => (field.secret ? "password" : KIND_TYPE[field.kind] || "text");

// Only what the person changed goes to the server: every plain field, and a secret only when something was typed.
function values() {
	const out = {};
	for (const field of props.card.fields) {
		if (!field.secret || String(form[field.key] || "").trim())
			out[field.key] = form[field.key];
	}
	return out;
}

async function persist() {
	const card = await integrationsApi.save(props.card.provider, values());
	fill(card);
	emit("update", card);
}

async function save() {
	busy.value = true;
	error.value = "";
	notice.value = "";
	try {
		await persist();
		notice.value = "Saved.";
	} catch (e) {
		error.value = serverMessage(e, "The details could not be saved.");
	} finally {
		busy.value = false;
	}
}

async function test() {
	busy.value = true;
	error.value = "";
	notice.value = "";
	try {
		await persist();
		const result = await integrationsApi.check(props.card.provider);
		emit("update", result.card);
		notice.value = result.ok ? result.message : "";
	} catch (e) {
		error.value = serverMessage(e, "The connection could not be tested.");
	} finally {
		busy.value = false;
	}
}
</script>
