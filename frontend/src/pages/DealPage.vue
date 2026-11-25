<template>
	<PageTemplate shape="record" data-testid="sellos-deal-page">
		<template #header>
			<RecordHeader
				:title="deal ? `${deal.client_name}, ${deal.target}` : 'Deal'"
				:line="line"
				back-to="/crm/deals"
				back-label="Back to deals"
				title-testid="sellos-deal-title"
			>
				<template v-if="deal" #status>
					<StatusBadge
						:tone="deal.approval_status === 'Approved' ? 'success' : 'warning'"
						:label="deal.approval_status"
						data-testid="sellos-deal-status"
					/>
				</template>
				<template v-if="deal" #actions>
					<AppButton
						v-if="deal.approval_status !== 'Approved'"
						type="button"
						variant="primary"
						data-testid="sellos-deal-approve"
						@click="approve"
					>
						Approve the split
					</AppButton>
					<AppButton
						v-else
						type="button"
						data-testid="sellos-deal-reopen"
						@click="reopen"
					>
						Reopen the split
					</AppButton>
				</template>
			</RecordHeader>
		</template>

		<LoadError
			v-if="loadError"
			:message="loadError"
			data-testid="sellos-deal-load-error"
			@retry="load"
		/>
		<LoadingSkeleton v-else-if="!loaded" :rows="4" label="Loading the deal." />
		<EmptyState
			v-else-if="!deal"
			title="This deal was not found"
			text="It may be archived, or you may not be allowed to see it."
			icon="lucide-handshake"
		/>

		<template v-if="deal">
			<p v-if="error" role="alert" data-testid="sellos-deal-error" class="ui-text-error">
				{{ error }}
			</p>
			<p v-if="notice" role="status" data-testid="sellos-deal-notice" class="ui-text-small">
				{{ notice }}
			</p>

			<SectionCard title="Deal">
				<dl>
					<FieldGrid>
						<ReadField label="Client" :value="deal.client_name" />
						<ReadField label="Unit or property" :value="deal.target" />
						<ReadField
							label="Price"
							:value="deal.price ? formatMoney(deal.price) : ''"
							data-testid="sellos-deal-money"
						/>
						<ReadField
							label="Commission"
							:value="
								deal.commission_amount ? formatMoney(deal.commission_amount) : ''
							"
						/>
						<ReadField label="Deal date" :value="formatDate(deal.deal_date)" />
					</FieldGrid>
				</dl>
			</SectionCard>

			<SectionCard title="Commission split" help="The shares add up to 100 percent.">
				<p v-if="!deal.splits.length" class="ui-text-muted">Not filled in</p>
				<ul class="space-y-1" data-testid="sellos-deal-splits">
					<li
						v-for="(s, n) in deal.splits"
						:key="n"
						data-testid="sellos-deal-split"
						:data-party="s.party_type"
						class="ui-text-small"
					>
						{{ s.party_type }}: {{ s.party }}, {{ s.percent }}% ({{
							formatMoney(s.amount)
						}})
					</li>
				</ul>
			</SectionCard>
		</template>

		<template #side>
			<SectionCard title="Approval">
				<template v-if="deal">
					<p
						v-if="deal.approval_status === 'Approved'"
						class="ui-text-muted"
						data-testid="sellos-deal-approved"
					>
						Approved by {{ deal.approved_by_name }} on
						{{ formatDateTime(deal.approved_on) }}. The split is kept unless it is
						reopened.
					</p>
					<p v-else class="ui-text-muted">
						The split waits for a Company Admin to approve it.
					</p>
				</template>
				<p v-else class="ui-text-muted">The deal is loading.</p>
			</SectionCard>
			<SectionCard title="Summary">
				<dl v-if="deal">
					<FieldGrid :columns="1">
						<ReadField label="Status" :value="deal.approval_status" />
						<ReadField
							label="Parties in the split"
							:value="deal.splits.length ? String(deal.splits.length) : ''"
						/>
						<ReadField label="Approved by" :value="deal.approved_by_name" />
					</FieldGrid>
				</dl>
				<p v-else class="ui-text-muted">No summary yet.</p>
			</SectionCard>
		</template>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import FieldGrid from "../components/FieldGrid.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageTemplate from "../components/PageTemplate.vue";
import ReadField from "../components/ReadField.vue";
import RecordHeader from "../components/RecordHeader.vue";
import SectionCard from "../components/SectionCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { dealApi } from "../crm/dealsApi";
import { formatDate, formatDateTime, formatMoney } from "../format";

// One deal (SOS-P4-06). There is no call that returns a single deal, so the page loads the list the Deals page
// loads and picks its record by name. Approving and reopening the split are made on the server and read back.
const route = useRoute();
const deal = ref(null);
const error = ref("");
const notice = ref("");
const loadError = ref("");
const loaded = ref(false);

const line = computed(() =>
	deal.value && deal.value.price ? `Price ${formatMoney(deal.value.price)}` : ""
);

async function load() {
	loadError.value = "";
	try {
		const result = await dealApi.overview();
		deal.value = result.deals.find((d) => d.name === route.params.name) || null;
	} catch (e) {
		loadError.value = serverMessage(e, "The deal could not be loaded.");
	} finally {
		loaded.value = true;
	}
}

async function run(action, done, failed) {
	error.value = "";
	notice.value = "";
	try {
		await action();
		notice.value = done;
		await load();
	} catch (e) {
		error.value = serverMessage(e, failed);
	}
}

const approve = () =>
	run(
		() => dealApi.approve(deal.value.name),
		`${deal.value.client_name}: the split is approved.`,
		"The split could not be approved."
	);

const reopen = () =>
	run(
		() => dealApi.reopen(deal.value.name),
		`${deal.value.client_name}: the split is reopened and waits for approval.`,
		"The split could not be reopened."
	);

onMounted(load);
</script>
