<template>
	<!-- A settings page with no list: the header card, then headed cards for each form. -->
	<PageTemplate data-testid="sellos-telephony-page">
		<template #header>
			<PageHeader
				title="Telephony"
				text="Enter your Plivo India account once, so calling works for your company. The keys are stored encrypted and never shown again."
				icon="lucide-phone"
			/>
		</template>

		<template v-if="!loading && !loadError" #kpis>
			<KpiStrip :items="kpis" />
		</template>

		<div v-if="loadError" data-testid="sellos-telephony-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<LoadingSkeleton v-else-if="loading" />

		<template v-else>
			<form class="ui-card" data-testid="sellos-telephony-form" @submit.prevent="save">
				<FormSection title="Plivo account">
					<FormField
						v-model="form.authId"
						type="password"
						label="Auth ID"
						autocomplete="off"
						:placeholder="state.auth_id_set ? 'Saved. Type to replace it.' : ''"
						data-testid="sellos-telephony-auth-id"
					/>
					<FormField
						v-model="form.authToken"
						type="password"
						label="Auth token"
						autocomplete="off"
						:placeholder="state.auth_token_set ? 'Saved. Type to replace it.' : ''"
						data-testid="sellos-telephony-auth-token"
					/>
					<FormField
						v-model="form.phoneNumber"
						type="tel"
						label="022 number"
						inputmode="tel"
						placeholder="022 followed by eight digits"
						class="md:col-span-2"
						data-testid="sellos-telephony-number"
					/>
				</FormSection>
				<div class="mt-ui-md space-y-ui-sm">
					<p class="text-sm text-ink-muted" data-testid="sellos-telephony-status">
						{{ statusText }}
					</p>
					<p
						v-if="error"
						data-testid="sellos-telephony-error"
						role="alert"
						class="text-sm text-danger"
					>
						{{ error }}
					</p>
					<p v-if="saved" data-testid="sellos-telephony-saved" class="text-sm text-ink">
						Saved.
					</p>
					<p
						v-if="result"
						:data-testid="
							result.ok ? 'sellos-telephony-test-ok' : 'sellos-telephony-test-error'
						"
						:role="result.ok ? 'status' : 'alert'"
						:class="result.ok ? 'text-sm text-ink' : 'text-sm text-danger'"
					>
						{{ result.message }}
					</p>
					<div class="flex flex-wrap items-center gap-ui-sm">
						<AppButton
							type="button"
							data-testid="sellos-telephony-test"
							:disabled="testing"
							@click="test"
						>
							Test connection
						</AppButton>
						<AppButton
							type="submit"
							variant="primary"
							data-testid="sellos-telephony-save"
						>
							Save
						</AppButton>
					</div>
				</div>
			</form>
		</template>
		<CallingRules v-if="!loading && !loadError" />
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { logRequestError } from "../api";
import AppButton from "../components/AppButton.vue";
import CallingRules from "../components/CallingRules.vue";
import FormField from "../components/FormField.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import FormSection from "../components/FormSection.vue";
import KpiStrip from "../components/KpiStrip.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import { serverMessage } from "../crm/crmApi";
import { telephonyApi } from "../telephony/telephonyApi";

const state = ref({ auth_id_set: false, auth_token_set: false, phone_number: "" });
const form = reactive({ authId: "", authToken: "", phoneNumber: "" });
const loading = ref(true);
const loadError = ref("");
const error = ref("");
const saved = ref(false);
const testing = ref(false);
const result = ref(null);

const kpis = computed(() => [
	{
		label: "Auth ID",
		value: state.value.auth_id_set ? "Saved" : "Not set",
		caption: "the Plivo account ID",
		icon: "lucide-key-round",
		tone: state.value.auth_id_set ? "success" : "warning",
	},
	{
		label: "Auth token",
		value: state.value.auth_token_set ? "Saved" : "Not set",
		caption: "stored encrypted",
		icon: "lucide-lock",
		tone: state.value.auth_token_set ? "success" : "warning",
	},
	{
		label: "022 number",
		value: state.value.phone_number || "Not set",
		caption: "for service calls",
		icon: "lucide-phone",
	},
]);

const statusText = computed(() => {
	const s = state.value;
	const set = (value) => (value ? "saved" : "not set");
	return `Auth ID: ${set(s.auth_id_set)}. Auth token: ${set(s.auth_token_set)}.`;
});

function apply(next) {
	state.value = next;
	form.phoneNumber = next.phone_number || "";
}

async function load() {
	loading.value = true;
	loadError.value = "";
	try {
		apply(await telephonyApi.get());
	} catch (e) {
		loadError.value = serverMessage(e, "Telephony settings could not be loaded.");
		logRequestError("telephony settings failed", e);
	} finally {
		loading.value = false;
	}
}

async function save() {
	error.value = "";
	saved.value = false;
	result.value = null;
	try {
		apply(await telephonyApi.save(form));
		// The keys are never shown again, so the boxes are emptied as soon as they are saved.
		form.authId = "";
		form.authToken = "";
		saved.value = true;
	} catch (e) {
		error.value = serverMessage(e, "The settings could not be saved.");
	}
}

async function test() {
	testing.value = true;
	result.value = null;
	try {
		result.value = await telephonyApi.check();
	} catch (e) {
		result.value = {
			ok: false,
			message: serverMessage(e, "The connection test failed. Try again."),
		};
	} finally {
		testing.value = false;
	}
}

onMounted(load);
</script>
