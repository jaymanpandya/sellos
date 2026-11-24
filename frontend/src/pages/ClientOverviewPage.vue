<template>
	<PageTemplate data-testid="sellos-client-overview-page">
		<template #header>
			<PageHeader
				title="Your dealings"
				text="Your shortlists, site visits, deal and sale, in one place."
				icon="lucide-layout-dashboard"
			/>
		</template>
		<template v-if="view && !loadError && kpis.length" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-client-overview-stats" />
		</template>

		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-client-overview-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<div v-if="view" class="space-y-ui-md">
			<template v-if="isBuyer">
				<ListCard title="Your search" data-testid="sellos-client-buyer">
					<p
						v-for="(row, i) in view.buyer.stages"
						:key="i"
						class="text-base text-ink"
						data-testid="sellos-client-buyer-stage"
					>
						Where you are: <strong>{{ row.stage }}</strong>
						<span class="text-ink-muted">, since {{ formatWhen(row.stage_on) }}</span>
					</p>
				</ListCard>

				<DataTable
					title="Shortlists"
					:columns="shortlistColumns"
					:rows="view.shortlists"
					:row-to="shortlistTo"
					empty-title="No shortlist yet"
					empty-text="Your agent will share homes with you here."
					empty-icon="lucide-list-checks"
					testid="sellos-client-overview-shortlists"
					row-testid="sellos-client-overview-shortlist"
					empty-testid="sellos-client-overview-shortlists-empty"
				>
					<template #cell-title="{ row }">{{ row.title }}</template>
					<template #cell-item_count="{ row }">{{ row.item_count }} homes</template>
				</DataTable>

				<DataTable
					title="Site visits"
					:columns="visitColumns"
					:rows="keyed(view.buyer.visits)"
					row-key="_k"
					empty-title="No site visit yet"
					empty-text="A visit your agent books will show here."
					empty-icon="lucide-map-pin"
					testid="sellos-client-visits"
					row-testid="sellos-client-visit"
					empty-testid="sellos-client-visits-empty"
				>
					<template #cell-when="{ row }">{{ formatWhen(row.when) }}</template>
					<template #cell-status="{ row }">
						<StatusBadge
							:tone="row.status === 'Done' ? 'success' : 'info'"
							:label="row.status"
						/>
					</template>
				</DataTable>

				<DataTable
					title="Your deal"
					:columns="dealColumns"
					:rows="keyed(view.buyer.deals)"
					row-key="_k"
					empty-title="No deal has been recorded yet"
					empty-icon="lucide-handshake"
					testid="sellos-client-deals"
					row-testid="sellos-client-deal"
					empty-testid="sellos-client-deals-empty"
				>
					<template #cell-status="{ row }">
						<StatusBadge
							:tone="row.status === 'Booked' ? 'success' : 'danger'"
							:label="row.status"
						/>
					</template>
				</DataTable>
			</template>

			<template v-for="(seller, i) in view.sellers" :key="i">
				<ListCard
					:title="seller.property ? `Your sale: ${seller.property}` : 'Your sale'"
					data-testid="sellos-client-seller"
				>
					<p class="text-base text-ink">
						Where it is: <strong>{{ seller.stage }}</strong>
					</p>
					<h3 class="ui-card-heading mt-ui-md">Mandate</h3>
					<p v-if="!seller.mandate" class="mt-ui-sm text-sm text-ink-muted">
						No mandate has been made yet.
					</p>
					<div
						v-else
						class="mt-ui-sm flex flex-wrap items-center gap-3"
						data-testid="sellos-client-mandate"
					>
						<span class="text-sm text-ink">
							{{ seller.mandate.type }}, {{ seller.mandate.term_months }} months
						</span>
						<StatusBadge
							:tone="seller.mandate.status === 'Signed' ? 'success' : 'warning'"
							:label="seller.mandate.status"
							data-testid="sellos-client-mandate-status"
						/>
					</div>
					<div
						v-if="seller.mandate"
						class="mt-ui-sm"
						data-testid="sellos-client-dossier"
					>
						<p v-if="!seller.mandate.dossier_released" class="text-sm text-ink-muted">
							The Dossier is available once the mandate is signed.
						</p>
						<ul v-else class="list-disc pl-5 text-sm text-ink">
							<li v-for="(item, k) in seller.mandate.dossier" :key="k">
								{{ item.title }}
							</li>
						</ul>
					</div>
					<EmptyState
						v-if="!seller.has_property"
						class="mt-ui-md"
						title="Your agent is linking your property"
						text="Enquiries will show here once it is linked."
						icon="lucide-link"
					/>
				</ListCard>
				<!-- Four fields a row and nothing else: label, stage, time stamp, SLA badge (SOS-P5-05). -->
				<DataTable
					v-if="seller.has_property"
					title="Enquiries on your property"
					:columns="enquiryColumns"
					:rows="seller.enquiries"
					row-key="label"
					empty-title="No enquiry yet"
					empty-text="Enquiries on your property will show here."
					empty-icon="lucide-inbox"
					:testid="`sellos-client-enquiries-${i}`"
					row-testid="sellos-client-enquiry"
					:empty-testid="`sellos-client-enquiries-${i}-empty`"
				>
					<template #cell-label="{ row }">
						<span
							class="font-medium text-ink"
							data-testid="sellos-client-enquiry-label"
						>
							{{ row.label }}
						</span>
					</template>
					<template #cell-stage="{ row }">
						<span data-testid="sellos-client-enquiry-stage">{{ row.stage }}</span>
					</template>
					<template #cell-stage_on="{ row }">{{ formatWhen(row.stage_on) }}</template>
					<template #cell-sla="{ row }">
						<StatusBadge
							:tone="row.sla === 'In SLA' ? 'success' : 'danger'"
							:label="`Response: ${row.sla}`"
							data-testid="sellos-client-enquiry-sla"
						/>
					</template>
				</DataTable>
			</template>

			<EmptyState
				v-if="!isBuyer && !view.sellers.length"
				title="Nothing to show yet"
				text="Your agent will add your search or your sale here."
				icon="lucide-layout-dashboard"
			/>
		</div>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import DataTable from "../components/DataTable.vue";
import EmptyState from "../components/EmptyState.vue";
import KpiStrip from "../components/KpiStrip.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { formatWhen } from "../format";
import { clientViewApi } from "../inventory/inventoryApi";

// What a client sees of their own dealings (SOS-P5-05). A buyer sees shortlists, visits and deal status; a seller
// sees mandate status, the Dossier once the mandate is signed, and the enquiries on their property as four plain
// fields each. The server returns nothing else.
const view = ref(null);
const loadError = ref("");

const shortlistColumns = [
	{ key: "title", label: "Shortlist", primary: true },
	{ key: "item_count", label: "Homes" },
];
const visitColumns = [
	{ key: "project", label: "Project", primary: true },
	{ key: "when", label: "When" },
	{ key: "status", label: "Status" },
];
const dealColumns = [
	{ key: "target", label: "Home", primary: true },
	{ key: "status", label: "Status" },
];
const enquiryColumns = [
	{ key: "label", label: "Enquiry", primary: true },
	{ key: "stage", label: "Stage" },
	{ key: "stage_on", label: "Since" },
	{ key: "sla", label: "Response" },
];
// DataTable needs a unique key for each row, and these rows have no id.
const keyed = (rows) => rows.map((r, i) => ({ ...r, _k: i }));
const shortlistTo = (s) => `/client/shortlists/${encodeURIComponent(s.name)}`;

// Numbers the server already returned, nothing more.
const kpis = computed(() => {
	const v = view.value;
	if (!v) return [];
	const items = [];
	if (isBuyer.value) {
		items.push(
			{
				label: "Shortlists",
				value: v.shortlists.length,
				caption: "Homes your agent chose",
				icon: "lucide-list-checks",
			},
			{
				label: "Site visits",
				value: v.buyer.visits.length,
				caption: "Booked or done",
				icon: "lucide-map-pin",
			},
			{
				label: "Deals",
				value: v.buyer.deals.length,
				caption: "Recorded for you",
				icon: "lucide-handshake",
			}
		);
	}
	if (v.sellers.length) {
		items.push({
			label: "Enquiries",
			value: v.sellers.reduce((n, s) => n + s.enquiries.length, 0),
			caption: "On your property",
			icon: "lucide-inbox",
		});
	}
	return items;
});

const isBuyer = computed(() => {
	const v = view.value;
	return Boolean(
		v &&
			(v.buyer.stages.length ||
				v.buyer.visits.length ||
				v.buyer.deals.length ||
				v.shortlists.length)
	);
});

async function load() {
	loadError.value = "";
	try {
		view.value = await clientViewApi.overview();
	} catch (e) {
		loadError.value = serverMessage(e, "Your dealings could not be loaded.");
	}
}

onMounted(load);
</script>
