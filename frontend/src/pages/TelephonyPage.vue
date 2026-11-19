<template>
	<div class="max-w-3xl" data-testid="sellos-telephony-page">
		<h1 class="ui-page-title">Telephony</h1>
		<p class="mt-2 text-ink-muted">
			Enter your Plivo India account once, so calling works for your company. The keys are
			stored encrypted and are never shown again after you save them.
		</p>

		<p
			v-if="loadError"
			data-testid="sellos-telephony-load-error"
			role="alert"
			class="mt-4 text-accent"
		>
			{{ loadError }}
		</p>
		<p v-else-if="loading" class="mt-4 text-ink-muted">Loading.</p>

		<form
			v-else
			class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4"
			data-testid="sellos-telephony-form"
			@submit.prevent="save"
		>
			<label class="block">
				<span class="block text-sm text-ink-muted">Auth ID</span>
				<input
					v-model="form.authId"
					type="password"
					autocomplete="off"
					data-testid="sellos-telephony-auth-id"
					class="field"
					:placeholder="state.auth_id_set ? 'Saved. Type to replace it.' : ''"
				/>
			</label>
			<label class="block">
				<span class="block text-sm text-ink-muted">Auth token</span>
				<input
					v-model="form.authToken"
					type="password"
					autocomplete="off"
					data-testid="sellos-telephony-auth-token"
					class="field"
					:placeholder="state.auth_token_set ? 'Saved. Type to replace it.' : ''"
				/>
			</label>
			<label class="block">
				<span class="block text-sm text-ink-muted">022 number</span>
				<input
					v-model="form.phoneNumber"
					inputmode="tel"
					data-testid="sellos-telephony-number"
					class="field"
					placeholder="022 followed by eight digits"
				/>
			</label>
			<p class="text-sm text-ink-muted" data-testid="sellos-telephony-status">
				{{ statusText }}
			</p>
			<p
				v-if="error"
				data-testid="sellos-telephony-error"
				role="alert"
				class="text-sm text-accent"
			>
				{{ error }}
			</p>
			<p v-if="saved" data-testid="sellos-telephony-saved" class="text-sm text-ink">
				Saved.
			</p>
			<div class="flex items-center gap-3">
				<button type="submit" class="btn" data-testid="sellos-telephony-save">Save</button>
				<button
					type="button"
					class="rounded-input px-3 py-2 text-sm text-ink-muted hover:bg-brand-light"
					data-testid="sellos-telephony-test"
					:disabled="testing"
					@click="test"
				>
					Test connection
				</button>
			</div>
			<p
				v-if="result"
				:data-testid="
					result.ok ? 'sellos-telephony-test-ok' : 'sellos-telephony-test-error'
				"
				:role="result.ok ? 'status' : 'alert'"
				:class="result.ok ? 'text-sm text-ink' : 'text-sm text-accent'"
			>
				{{ result.message }}
			</p>
		</form>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { logRequestError } from "../api";
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
