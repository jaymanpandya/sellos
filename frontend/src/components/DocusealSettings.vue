<template>
	<div class="space-y-4" data-testid="sellos-docuseal-settings">
		<p class="ui-text-muted">
			DocuSeal sends the mandate to the seller and your signer by email and keeps an audit
			trail. It is an electronic signature, not an Aadhaar eSign: your counsel decides
			whether it is enough.
		</p>
		<p v-if="error" role="alert" class="ui-text-error" data-testid="sellos-docuseal-error">
			{{ error }}
		</p>
		<p v-if="notice" role="status" class="ui-text-small" data-testid="sellos-docuseal-notice">
			{{ notice }}
		</p>
		<div class="grid gap-4 md:grid-cols-2">
			<FormField
				v-model="form.url"
				label="DocuSeal address"
				hint="https://api.docuseal.com, or the address of your own DocuSeal."
				data-testid="sellos-docuseal-url"
			/>
			<FormField
				v-model="form.api_key"
				type="password"
				:label="`API key${view.has_api_key ? ' (saved, leave empty to keep it)' : ''}`"
				data-testid="sellos-docuseal-key"
			/>
			<FormField
				v-model="form.webhook_secret"
				type="password"
				:label="`Webhook secret${
					view.has_webhook_secret ? ' (saved, leave empty to keep it)' : ''
				}`"
				hint="Any long random text. Enter the same text in DocuSeal's webhook header."
				data-testid="sellos-docuseal-secret"
			/>
			<FormField
				v-model="form.signer_name"
				label="Company signer name"
				data-testid="sellos-docuseal-signer-name"
			/>
			<FormField
				v-model="form.signer_email"
				type="email"
				label="Company signer email"
				data-testid="sellos-docuseal-signer-email"
			/>
		</div>
		<dl>
			<FieldGrid>
				<ReadField label="Webhook address" :value="view.webhook_url" />
				<ReadField label="Webhook header name" :value="view.webhook_header" />
			</FieldGrid>
		</dl>
		<div class="flex flex-wrap gap-2">
			<AppButton
				type="button"
				variant="primary"
				data-testid="sellos-docuseal-save"
				@click="save"
			>
				Save DocuSeal settings
			</AppButton>
			<AppButton
				type="button"
				:disabled="!view.connected"
				data-testid="sellos-docuseal-check"
				@click="check"
			>
				Test the connection
			</AppButton>
			<StatusBadge
				:tone="view.connected ? 'success' : 'warning'"
				:label="view.connected ? 'Connected' : 'Not connected'"
				data-testid="sellos-docuseal-state"
			/>
		</div>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import AppButton from "./AppButton.vue";
import FieldGrid from "./FieldGrid.vue";
import FormField from "./FormField.vue";
import ReadField from "./ReadField.vue";
import StatusBadge from "./StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { docusealApi } from "../crm/docusealApi";

// The company's DocuSeal connection (SOS-LOOP): address, API key, webhook secret and the company's signer. The key
// and the secret are sent to the server and never read back; the page only learns that they are set.
const view = reactive({
	url: "",
	has_api_key: false,
	has_webhook_secret: false,
	connected: false,
	webhook_url: "",
	webhook_header: "",
});
const form = reactive({
	url: "",
	api_key: "",
	webhook_secret: "",
	signer_name: "",
	signer_email: "",
});
const error = ref("");
const notice = ref("");

function show(result) {
	Object.assign(view, result);
	Object.assign(form, {
		url: result.url,
		api_key: "",
		webhook_secret: "",
		signer_name: result.signer_name,
		signer_email: result.signer_email,
	});
}

async function load() {
	try {
		show(await docusealApi.settings());
	} catch (e) {
		error.value = serverMessage(e, "The DocuSeal settings could not be loaded.");
	}
}

async function save() {
	error.value = "";
	notice.value = "";
	try {
		show(await docusealApi.saveSettings({ ...form }));
		notice.value = "The DocuSeal settings are saved.";
	} catch (e) {
		error.value = serverMessage(e, "The settings could not be saved.");
	}
}

async function check() {
	error.value = "";
	notice.value = "";
	try {
		await docusealApi.check();
		notice.value = "DocuSeal answered: the address and the key work.";
	} catch (e) {
		error.value = serverMessage(e, "DocuSeal could not be reached.");
	}
}

onMounted(load);
</script>
