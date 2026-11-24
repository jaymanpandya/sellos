<template>
	<PageTemplate data-testid="sellos-client-shortlist-page">
		<template #header>
			<PageHeader
				:title="view ? view.title : 'Shortlist'"
				:text="view && view.note ? view.note : ''"
				icon="lucide-list-checks"
			/>
		</template>
		<template v-if="view" #kpis>
			<KpiStrip
				:items="[
					{
						label: 'Homes',
						value: view.items.length,
						caption: 'On this shortlist',
						icon: 'lucide-house',
					},
					{
						label: 'No longer available',
						value: view.items.filter((i) => i.unavailable).length,
						caption: 'Ask your agent for others',
						icon: 'lucide-circle-slash',
						tone: 'warning',
					},
				]"
				data-testid="sellos-client-shortlist-stats"
			/>
		</template>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-client-shortlist-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<template v-if="view">
			<ListCard title="Your agent">
				<p class="text-sm text-ink" data-testid="sellos-client-shortlist-agent">
					{{ view.agent.name }}
					<span v-if="view.agent.phone">, {{ view.agent.phone }}</span>
				</p>
				<a
					class="ui-link mt-ui-sm inline-block text-sm"
					:href="view.pdf"
					target="_blank"
					rel="noopener"
					data-testid="sellos-client-shortlist-pdf"
				>
					Download as a PDF
				</a>
			</ListCard>
			<ListCard title="Homes" class="mt-ui-md">
				<ol class="space-y-ui-sm">
					<li
						v-for="item in view.items"
						:key="item.name"
						class="rounded-card border border-line-soft p-ui-md"
						data-testid="sellos-client-shortlist-item"
						:data-title="item.title"
						:data-unavailable="item.unavailable"
					>
						<div class="flex flex-wrap items-center gap-3">
							<span class="font-medium text-ink">
								{{ item.position }}. {{ item.title }}
							</span>
							<span class="text-sm text-ink-muted">
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
						<p v-if="item.note" class="mt-ui-sm text-sm text-ink">{{ item.note }}</p>
						<div
							v-if="details[item.name]"
							class="mt-ui-sm space-y-ui-sm"
							data-testid="sellos-client-shortlist-detail"
						>
							<p class="text-sm text-ink-muted">
								{{
									[item.configuration, item.locality, item.property_type]
										.filter(Boolean)
										.join(", ")
								}}
								<span v-if="item.carpet_area">, {{ item.carpet_area }} sq ft</span>
							</p>
							<p v-if="item.description" class="text-sm text-ink">
								{{ item.description }}
							</p>
							<div class="flex flex-wrap gap-ui-sm">
								<img
									v-for="url in item.photos"
									:key="url"
									:src="url"
									alt="Photo of the home"
									class="h-32 rounded-control"
								/>
							</div>
						</div>
					</li>
				</ol>
			</ListCard>
		</template>
	</PageTemplate>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";

import AppButton from "../components/AppButton.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import KpiStrip from "../components/KpiStrip.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { formatMoney } from "../format";
import { shortlistApi } from "../inventory/inventoryApi";

// One of the client's shortlists. Opening a home tells the agent which one and when (SOS-P7-09).
const route = useRoute();
const view = ref(null);
const loadError = ref("");
const details = reactive({});

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
