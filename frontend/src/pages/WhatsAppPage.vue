<template>
	<div data-testid="sellos-whatsapp-page">
		<PageHeader
			title="WhatsApp"
			text="Conversations with your leads. A warning shows each lead's consent and never stops a message."
			icon="lucide-message-circle"
		/>
		<LoadError
			v-if="error"
			class="mb-ui-md"
			data-testid="sellos-whatsapp-load-error"
			:message="error"
			@retry="load"
		/>
		<LoadingSkeleton v-else-if="!rows" />

		<EmptyState
			v-else-if="!rows.length"
			title="No conversations yet."
			text="A conversation starts when a customer writes to your WhatsApp number, or when you send a template to a lead."
			icon="lucide-message-circle-off"
			data-testid="sellos-whatsapp-empty"
		/>

		<div v-else class="grid grid-cols-1 gap-ui-md lg:grid-cols-3">
			<ListCard title="Conversations">
				<ul class="space-y-ui-sm" data-testid="sellos-whatsapp-list">
					<li v-for="row in rows" :key="row.name">
						<AppButton
							type="button"
							class="!w-full !justify-between"
							:active="selected === row.name"
							data-testid="sellos-whatsapp-conversation"
							:data-lead="row.lead"
							:data-state="row.state"
							@click="open(row.name)"
						>
							{{ row.title }}
						</AppButton>
						<div class="mt-1 flex flex-wrap items-center gap-ui-sm">
							<StatusBadge
								:tone="toneOf(row.consent_warning)"
								:label="row.consent_status"
								data-testid="sellos-whatsapp-row-consent"
								:data-level="row.consent_warning"
							/>
							<span class="text-sm text-ink-muted">{{ row.state }}</span>
						</div>
					</li>
				</ul>
			</ListCard>

			<div class="lg:col-span-2">
				<EmptyState
					v-if="!thread"
					title="Choose a conversation."
					text="Its messages are shown here."
					icon="lucide-messages-square"
					data-testid="sellos-whatsapp-none"
				/>
				<ListCard v-else :title="thread.title">
					<div class="mb-ui-md flex flex-wrap items-center gap-ui-sm">
						<router-link
							:to="`/crm/leads/${thread.lead}`"
							class="ui-link text-sm"
							data-testid="sellos-whatsapp-lead"
							>Open the lead</router-link
						>
						<StatusBadge
							:tone="toneOf(thread.consent_warning)"
							:label="thread.consent_status"
							data-testid="sellos-whatsapp-consent"
							:data-level="thread.consent_warning"
						/>
						<StatusBadge
							:tone="thread.state === 'With a human' ? 'info' : 'neutral'"
							:label="thread.state"
							data-testid="sellos-whatsapp-state"
						/>
					</div>
					<p
						v-if="thread.consent_message"
						class="mb-ui-md text-sm"
						:class="
							thread.consent_warning === 'red'
								? 'text-tone-danger'
								: 'text-ink-muted'
						"
						data-testid="sellos-whatsapp-warning"
					>
						{{ thread.consent_message }}
					</p>
					<p
						v-if="thread.state === 'With a human'"
						class="mb-ui-md text-sm text-ink"
						data-testid="sellos-whatsapp-handoff-note"
					>
						Handed to {{ thread.handed_to }}.
						<span v-if="thread.handoff_note">{{ thread.handoff_note }}</span>
					</p>

					<ol class="mb-ui-md space-y-ui-sm" data-testid="sellos-whatsapp-thread">
						<li
							v-for="message in thread.messages"
							:key="message.name"
							class="rounded-input border border-line-soft p-ui-md"
							data-testid="sellos-whatsapp-message"
							:data-direction="message.direction"
							:data-status="message.status"
							:data-intent="message.intent || 'none'"
						>
							<p class="text-sm text-ink-muted">
								{{ message.direction === "Inbound" ? "Customer" : "You" }} ·
								{{ message.status }}
								<span v-if="message.intent"> · {{ message.intent }}</span>
							</p>
							<p class="text-ink" data-testid="sellos-whatsapp-body">
								{{ message.body }}
							</p>
							<p
								v-if="message.error"
								class="text-sm text-tone-danger"
								data-testid="sellos-whatsapp-message-error"
							>
								{{ message.error }}
							</p>
							<p
								v-if="message.consent_status"
								class="text-sm"
								:class="
									message.consent_warning === 'red'
										? 'text-tone-danger'
										: 'text-ink-muted'
								"
								data-testid="sellos-whatsapp-message-consent"
								:data-level="message.consent_warning"
							>
								Consent when sent: {{ message.consent_status }}.
								{{ message.consent_message }}
							</p>
						</li>
					</ol>

					<form class="space-y-ui-md" @submit.prevent="sendText">
						<FormField
							v-model="text"
							type="textarea"
							label="Message"
							data-testid="sellos-whatsapp-text"
							:hint="
								thread.window_open
									? ''
									: 'The 24 hour window is closed. Send a template instead.'
							"
						/>
						<div class="flex flex-wrap items-center gap-ui-sm">
							<AppButton
								type="submit"
								variant="primary"
								data-testid="sellos-whatsapp-send"
								:disabled="!thread.window_open || !text.trim() || sending"
							>
								Send
							</AppButton>
						</div>
					</form>

					<form class="mt-ui-md space-y-ui-md" @submit.prevent="sendTemplate">
						<FormField
							v-model="template"
							type="select"
							label="Template"
							:options="templateOptions"
							data-testid="sellos-whatsapp-template"
						/>
						<FormField
							v-if="placeholders"
							v-model="parameters"
							label="Fill in the parts that change, separated by commas"
							data-testid="sellos-whatsapp-parameters"
						/>
						<AppButton
							type="submit"
							data-testid="sellos-whatsapp-send-template"
							:disabled="!template || sending"
						>
							Send template
						</AppButton>
					</form>

					<p
						v-if="result"
						class="mt-ui-md text-sm"
						:class="result.ok ? 'text-ink' : 'text-tone-danger'"
						:role="result.ok ? 'status' : 'alert'"
						data-testid="sellos-whatsapp-result"
					>
						{{ result.text }}
					</p>

					<div class="mt-ui-lg space-y-ui-md border-t border-line-soft pt-ui-md">
						<FormField
							v-model="note"
							label="Note for the person taking over"
							data-testid="sellos-whatsapp-note"
						/>
						<div class="flex flex-wrap items-center gap-ui-sm">
							<AppButton
								type="button"
								data-testid="sellos-whatsapp-handoff"
								:disabled="thread.state === 'With a human'"
								@click="handOff"
							>
								Hand to a human
							</AppButton>
							<AppButton
								type="button"
								data-testid="sellos-whatsapp-close"
								:disabled="thread.state === 'Closed'"
								@click="closeConversation"
							>
								Close conversation
							</AppButton>
						</div>
					</div>
				</ListCard>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { whatsappApi } from "../whatsapp/whatsappApi";

// The WhatsApp inbox (SOS-P6-11). Red is an explicit stop request and amber is consent not established.
// Neither disables a send: only the server's consent function may refuse, and only when the company
// turned Consent enforcement on. The 24 hour window is WhatsApp's own rule, not consent.
const rows = ref(null);
const templates = ref([]);
const selected = ref("");
const thread = ref(null);
const error = ref("");
const text = ref("");
const template = ref("");
const parameters = ref("");
const note = ref("");
const result = ref(null);
const sending = ref(false);

const toneOf = (level) => (level === "red" ? "danger" : level === "amber" ? "warning" : "neutral");
const templateOptions = computed(() => [
	{ label: "Choose a template", value: "" },
	...templates.value.map((t) => ({ label: t.name, value: t.name })),
]);
const placeholders = computed(() => {
	const chosen = templates.value.find((t) => t.name === template.value);
	return Boolean(chosen && /\{\{\d+\}\}/.test(chosen.body));
});

async function load() {
	error.value = "";
	try {
		[rows.value, templates.value] = await Promise.all([
			whatsappApi.conversations(),
			whatsappApi.templates(),
		]);
		if (!selected.value && rows.value.length) await open(rows.value[0].name);
	} catch (e) {
		error.value = serverMessage(e, "WhatsApp conversations could not be loaded.");
	}
}

async function open(name) {
	selected.value = name;
	result.value = null;
	thread.value = await whatsappApi.conversation(name);
}

async function refresh() {
	rows.value = await whatsappApi.conversations();
	thread.value = await whatsappApi.conversation(selected.value);
}

function report(answer) {
	if (answer.refused) result.value = { ok: false, text: answer.reason };
	else if (answer.error) result.value = { ok: false, text: answer.error };
	else result.value = { ok: true, text: "Sent." };
}

async function send(values) {
	sending.value = true;
	result.value = null;
	try {
		report(await whatsappApi.send({ lead: thread.value.lead, ...values }));
		await refresh();
	} catch (e) {
		result.value = { ok: false, text: serverMessage(e, "The message could not be sent.") };
	} finally {
		sending.value = false;
	}
}

async function sendText() {
	await send({ text: text.value });
	if (result.value?.ok) text.value = "";
}

async function sendTemplate() {
	const list = placeholders.value ? parameters.value.split(",").map((part) => part.trim()) : [];
	await send({ template: template.value, parameters: list });
}

async function handOff() {
	try {
		await whatsappApi.handOff(selected.value, note.value);
		note.value = "";
		await refresh();
	} catch (e) {
		result.value = { ok: false, text: serverMessage(e, "The handoff did not work.") };
	}
}

async function closeConversation() {
	try {
		await whatsappApi.close(selected.value);
		await refresh();
	} catch (e) {
		result.value = { ok: false, text: serverMessage(e, "The conversation was not closed.") };
	}
}

onMounted(load);
</script>
