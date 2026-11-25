<template>
	<PageTemplate shape="record" data-testid="sellos-client-shortlist-page">
		<template #header>
			<RecordHeader
				:title="view ? view.title : 'Shortlist'"
				:line="view && view.note ? view.note : ''"
				back-to="/client/shortlists"
				back-label="Back to your shortlists"
			>
				<template v-if="view" #status>
					<StatusBadge
						:tone="unavailableCount ? 'warning' : 'success'"
						:label="unavailableCount ? 'Some homes are gone' : 'All homes available'"
					/>
				</template>
			</RecordHeader>
		</template>

		<div v-if="loadError" data-testid="sellos-client-shortlist-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<LoadingSkeleton v-else-if="!view" :rows="3" label="Loading your shortlist." />

		<SectionCard v-if="view" title="Homes">
			<ol class="ui-list">
				<li
					v-for="item in view.items"
					:key="item.name"
					data-testid="sellos-client-shortlist-item"
					:data-title="item.title"
					:data-unavailable="item.unavailable"
				>
					<div class="flex flex-wrap items-center gap-3">
						<span class="ui-text-strong"> {{ item.position }}. {{ item.title }} </span>
						<span class="ui-text-muted">
							{{ item.price ? formatMoney(item.price) : "Price on request" }}
						</span>
						<StatusBadge
							v-if="item.unavailable"
							tone="danger"
							:label="item.reason"
							data-testid="sellos-client-shortlist-unavailable"
						/>
						<AppButton
							type="button"
							data-testid="sellos-client-shortlist-open"
							@click="openItem(item)"
						>
							{{ details[item.name] ? "Hide details" : "View details" }}
						</AppButton>
					</div>
					<p v-if="item.note" class="mt-ui-sm ui-text-small">{{ item.note }}</p>
					<div
						v-if="details[item.name]"
						class="mt-ui-sm space-y-ui-sm"
						data-testid="sellos-client-shortlist-detail"
					>
						<p class="ui-text-muted">
							{{
								[item.configuration, item.locality, item.property_type]
									.filter(Boolean)
									.join(", ")
							}}
							<span v-if="item.carpet_area">, {{ item.carpet_area }} sq ft</span>
						</p>
						<p v-if="item.description" class="ui-text-small">
							{{ item.description }}
						</p>
						<div class="flex flex-wrap gap-ui-sm">
							<img
								v-for="url in item.photos"
								:key="url"
								:src="url"
								alt="Photo of the home"
								class="h-32"
							/>
						</div>
					</div>
				</li>
			</ol>
		</SectionCard>

		<template #side>
			<SectionCard title="Your agent">
				<template v-if="view">
					<p class="ui-text-small" data-testid="sellos-client-shortlist-agent">
						{{ view.agent.name }}
						<span v-if="view.agent.phone">, {{ view.agent.phone }}</span>
					</p>
					<a
						class="ui-link mt-ui-sm inline-block ui-text-small"
						:href="view.pdf"
						target="_blank"
						rel="noopener"
						data-testid="sellos-client-shortlist-pdf"
					>
						Download as a PDF
					</a>
				</template>
				<p v-else class="ui-text-muted">Your agent is loading.</p>
			</SectionCard>
			<SectionCard title="Summary">
				<dl v-if="view" data-testid="sellos-client-shortlist-stats">
					<FieldGrid :columns="1">
						<ReadField label="Homes" :value="String(view.items.length)" />
						<ReadField label="No longer available" :value="String(unavailableCount)" />
					</FieldGrid>
				</dl>
				<p v-else class="ui-text-muted">The summary is loading.</p>
			</SectionCard>
		</template>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";

import AppButton from "../components/AppButton.vue";
import FieldGrid from "../components/FieldGrid.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageTemplate from "../components/PageTemplate.vue";
import ReadField from "../components/ReadField.vue";
import RecordHeader from "../components/RecordHeader.vue";
import SectionCard from "../components/SectionCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { formatMoney } from "../format";
import { shortlistApi } from "../inventory/inventoryApi";

// One of the client's shortlists. Opening a home tells the agent which one and when (SOS-P7-09).
const route = useRoute();
const view = ref(null);
const loadError = ref("");
const details = reactive({});
const unavailableCount = computed(
	() => view.value?.items.filter((i) => i.unavailable).length || 0
);

async function load() {
	loadError.value = "";
	try {
		view.value = await shortlistApi.mineOne(route.params.name);
	} catch (e) {
		loadError.value = serverMessage(e, "This shortlist could not be opened.");
	}
}

async function openItem(item) {
	if (details[item.name]) {
		details[item.name] = false;
		return;
	}
	try {
		Object.assign(item, await shortlistApi.open(route.params.name, item.name));
		details[item.name] = true;
	} catch (e) {
		loadError.value = serverMessage(e, "This home could not be opened.");
	}
}

onMounted(load);
</script>
