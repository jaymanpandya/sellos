<template>
	<div class="max-w-3xl" data-testid="sellos-whatsapp-setup-page">
		<PageHeader
			title="WhatsApp setup"
			text="Connect your company's own WhatsApp number and list its message templates. The keys are stored encrypted and are never shown again after you save them."
			icon="lucide-message-circle"
		/>
		<div v-if="loadError" data-testid="sellos-whatsapp-setup-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<LoadingSkeleton v-else-if="loading" />

		<template v-else>
			<form
				class="ui-card space-y-ui-md"
				data-testid="sellos-whatsapp-setup-form"
				@submit.prevent="save"
			>
				<h2 class="ui-card-heading">Your number</h2>
				<FormField
					v-model="form.accessToken"
					type="password"
					label="Access token"
					autocomplete="off"
					:placeholder="state.access_token_set ? 'Saved. Type to replace it.' : ''"
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
				<p class="text-sm text-ink-muted" data-testid="sellos-whatsapp-setup-status">
					{{ statusText }}
				</p>
				<p
					v-if="error"
					role="alert"
					class="text-sm text-accent"
					data-testid="sellos-whatsapp-setup-error"
				>
					{{ error }}
				</p>
				<p v-if="saved" class="text-sm text-ink" data-testid="sellos-whatsapp-setup-saved">
					Saved.
				</p>
				<div class="flex flex-wrap items-center gap-ui-sm">
					<AppButton
						type="submit"
						variant="primary"
						data-testid="sellos-whatsapp-setup-save"
					>
						Save
					</AppButton>
					<AppButton
						type="button"
						data-testid="sellos-whatsapp-setup-test"
						:disabled="testing"
						@click="test"
					>
						Test connection
					</AppButton>
				</div>
				<p
					v-if="result"
					:data-testid="
						result.ok
							? 'sellos-whatsapp-setup-test-ok'
							: 'sellos-whatsapp-setup-test-error'
					"
					:role="result.ok ? 'status' : 'alert'"
					:class="result.ok ? 'text-sm text-ink' : 'text-sm text-accent'"
				>
					{{ result.message }}
				</p>
			</form>

			<form
				class="ui-card mt-ui-md space-y-ui-md"
				data-testid="sellos-whatsapp-template-form"
				@submit.prevent="saveTemplate"
			>
				<h2 class="ui-card-heading">Message templates</h2>
				<ul class="space-y-1" data-testid="sellos-whatsapp-template-list">
					<li
						v-for="t in templates"
						:key="t.name"
						class="text-sm text-ink"
						data-testid="sellos-whatsapp-template-row"
						:data-name="t.name"
					>
						{{ t.name }} · {{ t.status }}{{ t.enabled ? "" : " · off" }}
					</li>
				</ul>
				<FormField
					v-model="tpl.name"
					label="Template name"
					hint="Lower case letters, digits and underscores."
					data-testid="sellos-whatsapp-template-name"
				/>
				<FormField
					v-model="tpl.body"
					type="textarea"
					label="Message"
					hint="Use {{1}}, {{2}} for the parts that change."
					data-testid="sellos-whatsapp-template-body"
				/>
				<FormField
					v-model="tpl.status"
					type="select"
					label="Provider approval"
					:options="['Pending', 'Approved', 'Rejected']"
					data-testid="sellos-whatsapp-template-status"
				/>
				<p
					v-if="templateError"
					role="alert"
					class="text-sm text-accent"
					data-testid="sellos-whatsapp-template-error"
				>
					{{ templateError }}
				</p>
				<AppButton type="submit" data-testid="sellos-whatsapp-template-save">
					Save template
				</AppButton>
			</form>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { logRequestError } from "../api";
import AppButton from "../components/AppButton.vue";
import FormField from "../components/FormField.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
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
	} catch (e) {
		templateError.value = serverMessage(e, "The template could not be saved.");
	}
}

onMounted(load);
</script>
