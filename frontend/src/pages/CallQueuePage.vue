<template>
	<div data-testid="sellos-queue">
		<PageHeader title="Call queue" text="Who to call next." icon="lucide-phone" />
		<p class="mb-ui-md text-sm text-ink-muted" data-testid="sellos-queue-note">
			Consented leads come first, the soonest expiry first, then the rest. Every lead you may
			see is here, and a warning never stops a call.
		</p>
		<LoadError
			v-if="error"
			class="mb-ui-md"
			data-testid="sellos-queue-error"
			:message="error"
			@retry="load"
		/>
		<LoadingSkeleton v-else-if="!view" />

		<template v-if="view">
			<div
				class="mb-ui-md grid grid-cols-2 gap-ui-md md:grid-cols-4"
				data-testid="sellos-queue-stats"
			>
				<StatCard
					:label="view.total === 1 ? 'Lead in the queue' : 'Leads in the queue'"
					:value="view.total"
					icon="lucide-phone"
					data-testid="sellos-queue-count"
				/>
			</div>
			<EmptyState
				v-if="!view.leads.length"
				title="No leads to call."
				text="Leads you may see will be listed here."
				icon="lucide-phone-off"
				data-testid="sellos-queue-empty"
			/>
			<ListCard v-else title="Leads to call">
				<ol class="space-y-ui-sm" data-testid="sellos-queue-list">
					<li
						v-for="row in view.leads"
						:key="row.lead"
						class="rounded-card border border-line-soft bg-surface-faint p-ui-md"
						data-testid="sellos-queue-row"
						:data-lead="row.lead"
						:data-status="row.consent_status"
					>
						<div class="flex flex-wrap items-center justify-between gap-ui-sm">
							<div class="flex min-w-0 flex-wrap items-center gap-ui-sm">
								<span
									class="text-sm text-ink-muted"
									data-testid="sellos-queue-position"
									>{{ row.position }}</span
								>
								<router-link
									:to="`/crm/leads/${row.lead}`"
									class="ui-link font-medium"
									data-testid="sellos-queue-lead"
									>{{ row.lead_title }}</router-link
								>
								<span class="text-sm text-ink-muted">{{ row.stage }}</span>
								<StatusBadge
									:tone="toneOf(row.consent_warning)"
									:label="row.consent_status"
									data-testid="sellos-queue-consent"
									:data-level="row.consent_warning || 'none'"
									:title="row.consent_message"
								/>
								<span
									v-if="row.time_left"
									class="text-sm text-ink"
									data-testid="sellos-queue-time-left"
									>{{ row.time_left }} left</span
								>
								<span
									v-else-if="row.consent_status === 'Consented'"
									class="text-sm text-ink-muted"
									data-testid="sellos-queue-no-expiry"
									>No expiry</span
								>
							</div>
							<AppButton
								type="button"
								variant="primary"
								data-testid="sellos-queue-call"
								:aria-expanded="shown.has(row.lead)"
								@click="toggle(row.lead)"
							>
								<template #prefix
									><span
										class="lucide-phone icon-inherit size-4"
										aria-hidden="true"
								/></template>
								Call
							</AppButton>
						</div>
						<p
							v-if="row.consent_message"
							class="mt-ui-sm text-sm"
							:class="
								row.consent_warning === 'red'
									? 'text-tone-danger'
									: 'text-ink-muted'
							"
							data-testid="sellos-queue-warning"
						>
							{{ row.consent_message }}
						</p>
						<p
							v-if="shown.has(row.lead)"
							class="mt-ui-sm text-sm text-ink"
							data-testid="sellos-queue-number"
						>
							<template v-if="row.phone">
								<a
									v-if="view.full_numbers"
									:href="`tel:${row.phone}`"
									class="ui-link"
									>{{ row.phone }}</a
								>
								<span v-else>{{ row.phone }}</span>
								<span v-if="row.overseas_phone"> · {{ row.overseas_phone }}</span>
							</template>
							<template v-else>No phone</template>
						</p>
					</li>
				</ol>
			</ListCard>
		</template>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import StatCard from "../components/StatCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { crmApi, serverMessage } from "../crm/crmApi";

// The caller queue (SOS-P2-09). The order and the time left come from the server. A red mark is an
// explicit stop request, amber is consent not established. Neither hides a lead or disables Call.
const view = ref(null);
const error = ref("");
const shown = reactive(new Set());

const toneOf = (level) => (level === "red" ? "danger" : level === "amber" ? "warning" : "neutral");

function toggle(lead) {
	if (shown.has(lead)) shown.delete(lead);
	else shown.add(lead);
}

async function load() {
	error.value = "";
	try {
		view.value = await crmApi.callerQueue();
	} catch (e) {
		error.value = serverMessage(e, "The call queue could not be loaded.");
	}
}

onMounted(load);
</script>
