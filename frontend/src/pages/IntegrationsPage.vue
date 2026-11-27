<template>
	<PageTemplate shape="form" data-testid="sellos-integrations-page">
		<template #header>
			<PageHeader
				title="Integrations"
				text="Add your company's own provider keys, so your company runs on its own accounts. Every key is stored encrypted and is never shown again, only its last four characters."
				icon="lucide-plug"
			/>
		</template>

		<div v-if="loadError" data-testid="sellos-integrations-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<LoadingSkeleton v-else-if="loading" />

		<div v-else class="space-y-4">
			<IntegrationCard
				v-for="card in cards"
				:key="card.provider"
				:card="card"
				@update="replace"
			/>
			<SectionCard
				:title="voice.title"
				help="Calling is set up on the Telephony settings page, in one place only."
				data-testid="sellos-integration-voice"
			>
				<template #actions>
					<StatusBadge
						:tone="voice.configured ? 'success' : 'neutral'"
						:label="voice.configured ? 'Set' : 'Not set'"
					/>
				</template>
				<router-link
					:to="{ name: 'telephony' }"
					class="ui-link ui-text-strong"
					data-testid="sellos-integration-voice-link"
				>
					Open the Telephony settings
				</router-link>
			</SectionCard>
		</div>
	</PageTemplate>
</template>

<script setup>
import { onMounted, ref } from "vue";

import IntegrationCard from "../components/IntegrationCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import SectionCard from "../components/SectionCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { integrationsApi } from "../company/integrationsApi";
import { serverMessage } from "../crm/crmApi";

// Company settings, Integrations (SOS-INT-1): one card per provider, for a Company Admin only.
const cards = ref([]);
const voice = ref({ title: "Plivo and voice", configured: false });
const loading = ref(true);
const loadError = ref("");

async function load() {
	loading.value = true;
	loadError.value = "";
	try {
		const result = await integrationsApi.list();
		cards.value = result.providers;
		voice.value = result.voice;
	} catch (e) {
		loadError.value = serverMessage(e, "The integrations could not be loaded.");
	} finally {
		loading.value = false;
	}
}

function replace(card) {
	cards.value = cards.value.map((c) => (c.provider === card.provider ? card : c));
}

onMounted(load);
</script>
