<template>
	<div class="space-y-3" data-testid="sellos-signing">
		<div class="flex flex-wrap items-center gap-2">
			<SigningBadge :status="mandate.signing_status" />
			<AppButton
				v-if="mandate.signed_document && mandate.status === 'Signed'"
				type="button"
				data-testid="sellos-signing-download"
				@click="download(mandate.signed_document)"
			>
				Download signed copy
			</AppButton>
			<AppButton
				v-if="mandate.audit_trail"
				type="button"
				data-testid="sellos-signing-audit"
				@click="download(mandate.audit_trail)"
			>
				Audit trail
			</AppButton>
		</div>

		<ul v-if="mandate.signers.length" class="space-y-1" data-testid="sellos-signing-signers">
			<li
				v-for="s in mandate.signers"
				:key="s.role"
				class="ui-text-small"
				data-testid="sellos-signing-signer"
				:data-role="s.role"
			>
				<span class="ui-text-strong">{{ s.name }}</span> ({{ s.role }}):
				{{ s.status }}
				<span v-if="s.completed_on" class="ui-text-muted">
					, {{ formatWhen(s.completed_on) }}</span
				>
				<span v-else-if="s.viewed_on" class="ui-text-muted">
					, viewed {{ formatWhen(s.viewed_on) }}</span
				>
				<span v-else-if="s.sent_on" class="ui-text-muted">
					, sent {{ formatWhen(s.sent_on) }}</span
				>
			</li>
		</ul>

		<template v-if="mandate.status !== 'Signed' && !mandate.archived">
			<p
				v-if="connected === false"
				class="ui-text-muted"
				data-testid="sellos-signing-connect"
			>
				DocuSeal is not connected.
				<router-link v-if="isAdmin" :to="settingsPath" class="ui-link">
					Connect DocuSeal
				</router-link>
				<span v-else>Ask a Company Admin to connect DocuSeal.</span>
			</p>
			<AppButton
				v-else-if="!['Sent', 'Viewed'].includes(mandate.signing_status)"
				type="button"
				variant="primary"
				:disabled="busy"
				data-testid="sellos-signing-send"
				@click="send"
			>
				{{
					["Declined", "Expired"].includes(mandate.signing_status)
						? "Send for signing again"
						: "Send for signing"
				}}
			</AppButton>
			<p v-else class="ui-text-muted">
				Waiting for the signers. The terms are locked until they answer.
			</p>
		</template>
		<p v-if="error" role="alert" class="ui-text-error" data-testid="sellos-signing-error">
			{{ error }}
		</p>
	</div>
</template>

<script setup>
// Electronic signing of a mandate through DocuSeal (SOS-LOOP): where signing stands, each signer, "Send for signing"
// (or "Connect DocuSeal" with a link to the settings when it is not set up), and the signed copy and audit trail
// once signed. The server does every step and judges every call.
import { computed, onMounted, ref } from "vue";

import AppButton from "./AppButton.vue";
import SigningBadge from "./SigningBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { docusealApi } from "../crm/docusealApi";
import { formatWhen } from "../format";
import { session } from "../session";

const props = defineProps({ mandate: { type: Object, required: true } });
const emit = defineEmits(["changed"]);

const connected = ref(null);
const settingsPath = ref("/company/integrations");
const busy = ref(false);
const error = ref("");
const isAdmin = computed(() => session.roles.includes("SellOS Company Admin"));

const download = (url) => window.open(url, "_blank", "noopener");

async function send() {
	busy.value = true;
	error.value = "";
	try {
		await docusealApi.send(props.mandate.name);
		emit("changed", "The mandate is sent for signing.");
	} catch (e) {
		error.value = serverMessage(e, "The mandate could not be sent for signing.");
	} finally {
		busy.value = false;
	}
}

onMounted(async () => {
	try {
		const status = await docusealApi.status();
		connected.value = status.connected;
		settingsPath.value = status.settings_path;
	} catch {
		connected.value = null;
	}
});
</script>
