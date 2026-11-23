<template>
	<div data-testid="sellos-client-overview-page">
		<PageHeader
			title="Your dealings"
			text="Your shortlists, site visits, deal and sale, in one place."
			icon="lucide-layout-dashboard"
		/>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-client-overview-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<template v-if="view">
			<ListCard v-if="isBuyer" title="Your search" data-testid="sellos-client-buyer">
				<p
					v-for="(row, i) in view.buyer.stages"
					:key="i"
					class="text-sm text-ink"
					data-testid="sellos-client-buyer-stage"
				>
					Where you are: <strong>{{ row.stage }}</strong>
					<span class="text-ink-muted">, since {{ whenText(row.stage_on) }}</span>
				</p>
				<h3 class="mt-ui-md text-sm font-semibold text-ink">Shortlists</h3>
				<EmptyState
					v-if="!view.shortlists.length"
					title="No shortlist yet"
					text="Your agent will share homes with you here."
					icon="lucide-list-checks"
				/>
				<ul class="space-y-ui-sm">
					<li
						v-for="s in view.shortlists"
						:key="s.name"
						data-testid="sellos-client-overview-shortlist"
					>
						<router-link
							:to="`/client/shortlists/${encodeURIComponent(s.name)}`"
							class="ui-link font-medium"
						>
							{{ s.title }}
						</router-link>
						<span class="text-sm text-ink-muted"> ({{ s.item_count }} homes)</span>
					</li>
				</ul>
				<h3 class="mt-ui-md text-sm font-semibold text-ink">Site visits</h3>
				<EmptyState
					v-if="!view.buyer.visits.length"
					title="No site visit yet"
					text="A visit your agent books will show here."
					icon="lucide-map-pin"
				/>
				<ul class="space-y-ui-sm">
					<li
						v-for="(v, i) in view.buyer.visits"
						:key="i"
						class="flex flex-wrap items-center gap-3"
						data-testid="sellos-client-visit"
					>
						<span class="text-sm text-ink"
							>{{ v.project }}, {{ whenText(v.when) }}</span
						>
						<StatusBadge
							:tone="v.status === 'Done' ? 'success' : 'info'"
							:label="v.status"
						/>
					</li>
				</ul>
				<h3 class="mt-ui-md text-sm font-semibold text-ink">Your deal</h3>
				<p v-if="!view.buyer.deals.length" class="text-sm text-ink-muted">
					No deal has been recorded yet.
				</p>
				<ul class="space-y-ui-sm">
					<li
						v-for="(d, i) in view.buyer.deals"
						:key="i"
						class="flex flex-wrap items-center gap-3"
						data-testid="sellos-client-deal"
					>
						<span class="text-sm text-ink">{{ d.target }}</span>
						<StatusBadge
							:tone="d.status === 'Booked' ? 'success' : 'danger'"
							:label="d.status"
						/>
					</li>
				</ul>
			</ListCard>

			<ListCard
				v-for="(seller, i) in view.sellers"
				:key="i"
				:title="seller.property ? `Your sale: ${seller.property}` : 'Your sale'"
				class="mt-ui-md"
				data-testid="sellos-client-seller"
			>
				<p class="text-sm text-ink">
					Where it is: <strong>{{ seller.stage }}</strong>
				</p>
				<h3 class="mt-ui-md text-sm font-semibold text-ink">Mandate</h3>
				<p v-if="!seller.mandate" class="text-sm text-ink-muted">
					No mandate has been made yet.
				</p>
				<div
					v-else
					class="flex flex-wrap items-center gap-3"
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
				<div v-if="seller.mandate" class="mt-ui-sm" data-testid="sellos-client-dossier">
					<p v-if="!seller.mandate.dossier_released" class="text-sm text-ink-muted">
						The Dossier is available once the mandate is signed.
					</p>
					<ul v-else class="list-disc pl-5 text-sm text-ink">
						<li v-for="(item, k) in seller.mandate.dossier" :key="k">
							{{ item.title }}
						</li>
					</ul>
				</div>
				<h3 class="mt-ui-md text-sm font-semibold text-ink">Enquiries on your property</h3>
				<EmptyState
					v-if="!seller.has_property"
					title="Your agent is linking your property"
					text="Enquiries will show here once it is linked."
					icon="lucide-link"
				/>
				<EmptyState
					v-else-if="!seller.enquiries.length"
					title="No enquiry yet"
					text="Enquiries on your property will show here."
					icon="lucide-inbox"
				/>
				<ul class="space-y-ui-sm">
					<li
						v-for="row in seller.enquiries"
						:key="row.label"
						class="flex flex-wrap items-center gap-3 rounded-input border border-line-soft p-ui-md"
						data-testid="sellos-client-enquiry"
					>
						<span
							class="font-medium text-ink"
							data-testid="sellos-client-enquiry-label"
						>
							{{ row.label }}
						</span>
						<span class="text-sm text-ink" data-testid="sellos-client-enquiry-stage">
							{{ row.stage }}
						</span>
						<span class="text-sm text-ink-muted"
							>since {{ whenText(row.stage_on) }}</span
						>
						<StatusBadge
							:tone="row.sla === 'In SLA' ? 'success' : 'danger'"
							:label="`Response: ${row.sla}`"
							data-testid="sellos-client-enquiry-sla"
						/>
					</li>
				</ul>
			</ListCard>

			<EmptyState
				v-if="!isBuyer && !view.sellers.length"
				title="Nothing to show yet"
				text="Your agent will add your search or your sale here."
				icon="lucide-layout-dashboard"
			/>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import EmptyState from "../components/EmptyState.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { clientViewApi, whenText } from "../inventory/inventoryApi";

// What a client sees of their own dealings (SOS-P5-05). A buyer sees shortlists, visits and deal status; a seller
// sees mandate status, the Dossier once the mandate is signed, and the enquiries on their property as four plain
// fields each. The server returns nothing else.
const view = ref(null);
const loadError = ref("");

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
