<template>
	<!-- A settings page: the header card, a headed card for the number, and the templates as a table. -->
	<PageTemplate shape="form" data-testid="sellos-whatsapp-setup-page">
		<template #header>
			<PageHeader
				title="WhatsApp setup"
				text="Connect your company's own WhatsApp number and list its message templates. The keys are stored encrypted and never shown again."
				icon="lucide-message-circle"
			>
				<AppButton
					v-if="!loading && !loadError"
					type="button"
					data-testid="sellos-whatsapp-template-add"
					@click="openTemplate"
				>
					<template #prefix
						><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
					/></template>
					Add template
				</AppButton>
			</PageHeader>
		</template>

		<template v-if="!loading && !loadError" #notice>
			<Notice title="Connection status">
				<p data-testid="sellos-whatsapp-setup-status">{{ statusText }}</p>
			</Notice>
		</template>

		<div v-if="loadError" data-testid="sellos-whatsapp-setup-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<LoadingSkeleton v-else-if="loading" />

		<div v-else class="space-y-4">
			<form data-testid="sellos-whatsapp-setup-form" @submit.prevent="save">
				<SectionCard
					title="Your number"
					help="The keys are stored encrypted and never shown again."
				>
					<FieldGrid>
						<FormField
							v-model="form.accessToken"
							type="password"
							label="Access token"
							autocomplete="off"
							:placeholder="
								state.access_token_set ? 'Saved. Type to replace it.' : ''
							"
							data-testid="sellos-whatsapp-setup-token"
						/>
						<FormField
							v-model="form.appSecret"
							type="password"
							label="Webhook signing secret"
							autocomplete="off"
							:placeholder="state.app_secret_set ? 'Saved. Type to replace it.' : ''"
							data-testid="sellos-whatsapp-setup-secret"
						/>
						<FormField
							v-model="form.phoneNumberId"
							label="Number ID"
							inputmode="numeric"
							data-testid="sellos-whatsapp-setup-number-id"
						/>
						<FormField
							v-model="form.displayNumber"
							type="tel"
							label="WhatsApp number"
							inputmode="tel"
							data-testid="sellos-whatsapp-setup-number"
						/>
					</FieldGrid>
					<div class="mt-4 space-y-2">
						<p
							v-if="error"
							role="alert"
							class="ui-text-error"
							data-testid="sellos-whatsapp-setup-error"
						>
							{{ error }}
						</p>
						<p
							v-if="saved"
							class="ui-text-small"
							data-testid="sellos-whatsapp-setup-saved"
						>
							Saved.
						</p>
						<p
							v-if="result"
							:data-testid="
								result.ok
									? 'sellos-whatsapp-setup-test-ok'
									: 'sellos-whatsapp-setup-test-error'
							"
							:role="result.ok ? 'status' : 'alert'"
							:class="result.ok ? 'ui-text-small' : 'ui-text-error'"
						>
							{{ result.message }}
						</p>
					</div>
					<template #footer>
						<AppButton
							type="button"
							data-testid="sellos-whatsapp-setup-test"
							:disabled="testing"
							@click="test"
						>
							Test connection
						</AppButton>
						<AppButton
							type="submit"
							variant="primary"
							data-testid="sellos-whatsapp-setup-save"
						>
							Save
						</AppButton>
					</template>
				</SectionCard>
			</form>

			<DataTable
				title="Message templates"
				caption="Message templates"
				:columns="templateColumns"
				:rows="templates"
				empty-title="No templates yet"
				empty-text="Add the first message template with Add template."
				empty-icon="lucide-message-square"
				testid="sellos-whatsapp-template-list"
				row-testid="sellos-whatsapp-template-row"
			>
				<template #cell-status="{ row }">
					<StatusBadge
						:label="row.status"
						:tone="TEMPLATE_TONE[row.status] || 'neutral'"
					/>
				</template>
				<template #cell-enabled="{ row }">
					<span class="ui-text-secondary">{{ row.enabled ? "On" : "Off" }}</span>
				</template>
			</DataTable>
		</div>

		<FormDrawer
			:open="addingTemplate"
			title="Add a message template"
			text="Templates are approved by the provider before they can start a conversation."
			submit-label="Save template"
			testid="sellos-whatsapp-template-form"
			submit-testid="sellos-whatsapp-template-save"
			@close="addingTemplate = false"
			@submit="saveTemplate"
		>
			<FormSection title="Template">
				<FormField
					v-model="tpl.name"
					label="Template name"
					hint="Lower case letters, digits and underscores."
					data-testid="sellos-whatsapp-template-name"
				/>
				<FormField
					v-model="tpl.status"
					type="select"
					label="Provider approval"
					:options="['Pending', 'Approved', 'Rejected']"
					data-testid="sellos-whatsapp-template-status"
				/>
				<FormField
					v-model="tpl.body"
					type="textarea"
					label="Message"
					hint="Use {{1}}, {{2}} for the parts that change."
					class="md:col-span-2"
					data-testid="sellos-whatsapp-template-body"
				/>
			</FormSection>
			<p
				v-if="templateError"
				role="alert"
				class="ui-text-error"
				data-testid="sellos-whatsapp-template-error"
			>
				{{ templateError }}
			</p>
		</FormDrawer>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { logRequestError } from "../api";
import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import FieldGrid from "../components/FieldGrid.vue";
import Notice from "../components/Notice.vue";
import SectionCard from "../components/SectionCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { whatsappApi, whatsappSetupApi } from "../whatsapp/whatsappApi";

const state = ref({ access_token_set: false, app_secret_set: false });
const form = reactive({ accessToken: "", appSecret: "", phoneNumberId: "", displayNumber: "" });
const templates = ref([]);
const tpl = reactive({ name: "", body: "", status: "Approved" });
const loading = ref(true);
const loadError = ref("");
const error = ref("");
const templateError = ref("");
const saved = ref(false);
const testing = ref(false);
const addingTemplate = ref(false);
const TEMPLATE_TONE = { Approved: "success", Pending: "warning", Rejected: "danger" };
const templateColumns = [
	{ key: "name", label: "Template", primary: true },
	{ key: "status", label: "Provider approval" },
	{ key: "enabled", label: "Sending" },
];
const result = ref(null);

const statusText = computed(() => {
	const s = state.value;
	const set = (value) => (value ? "saved" : "not set");
	return `Access token: ${set(s.access_token_set)}. Webhook signing secret: ${set(
		s.app_secret_set
	)}.`;
});

function apply(next) {
	state.value = next;
	form.phoneNumberId = next.phone_number_id || "";
	form.displayNumber = next.display_number || "";
}

async function load() {
	loading.value = true;
	loadError.value = "";
	try {
		apply(await whatsappSetupApi.get());
		templates.value = await whatsappApi.templates(1);
	} catch (e) {
		loadError.value = serverMessage(e, "WhatsApp setup could not be loaded.");
		logRequestError("whatsapp setup failed", e);
	} finally {
		loading.value = false;
	}
}

async function save() {
	error.value = "";
	saved.value = false;
	result.value = null;
	try {
		apply(await whatsappSetupApi.save(form));
		// The keys are never shown again, so the boxes are emptied as soon as they are saved.
		form.accessToken = "";
		form.appSecret = "";
		saved.value = true;
	} catch (e) {
		error.value = serverMessage(e, "The settings could not be saved.");
	}
}

async function test() {
	testing.value = true;
	result.value = null;
	try {
		result.value = await whatsappSetupApi.check();
	} catch (e) {
		result.value = {
			ok: false,
			message: serverMessage(e, "The connection test failed. Try again."),
		};
	} finally {
		testing.value = false;
	}
}

function openTemplate() {
	templateError.value = "";
	addingTemplate.value = true;
}

async function saveTemplate() {
	templateError.value = "";
	try {
		await whatsappSetupApi.saveTemplate({
			...tpl,
			language: "en",
			category: "Utility",
			enabled: 1,
		});
		templates.value = await whatsappApi.templates(1);
		tpl.name = "";
		tpl.body = "";
		addingTemplate.value = false;
	} catch (e) {
		templateError.value = serverMessage(e, "The template could not be saved.");
	}
}

onMounted(load);
</script>
