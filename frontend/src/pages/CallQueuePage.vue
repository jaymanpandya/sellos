<template>
	<div data-testid="sellos-queue">
		<h1 class="ui-page-title">Call queue</h1>
		<p class="ui-page-lead" data-testid="sellos-queue-note">
			Consented leads come first, the soonest expiry first, then the rest. Every lead you may
			see is here, and a warning never stops a call.
		</p>
		<p v-if="error" role="alert" data-testid="sellos-queue-error" class="mt-3 text-accent">
			{{ error }}
		</p>

		<template v-if="view">
			<p class="mt-3 text-sm text-ink-muted" data-testid="sellos-queue-count">
				{{ view.total }} {{ view.total === 1 ? "lead" : "leads" }} in the queue
			</p>
			<p
				v-if="!view.leads.length"
				class="mt-3 text-ink-muted"
				data-testid="sellos-queue-empty"
			>
				No leads to call.
			</p>
			<ol class="mt-3 space-y-2" data-testid="sellos-queue-list">
				<li
					v-for="row in view.leads"
					:key="row.lead"
					class="rounded-input border border-line bg-surface p-3"
					data-testid="sellos-queue-row"
					:data-lead="row.lead"
					:data-status="row.consent_status"
				>
					<div class="flex flex-wrap items-center justify-between gap-2">
						<div class="min-w-0">
							<span
								class="mr-2 text-sm text-ink-muted"
								data-testid="sellos-queue-position"
								>{{ row.position }}</span
							>
							<router-link
								:to="`/crm/leads/${row.lead}`"
								class="font-medium text-ink underline"
								data-testid="sellos-queue-lead"
								>{{ row.lead_title }}</router-link
							>
							<span class="ml-2 text-sm text-ink-muted">{{ row.stage }}</span>
							<span
								class="ml-2 rounded-input border px-2 py-1 text-xs"
								data-testid="sellos-queue-consent"
								:data-level="row.consent_warning || 'none'"
								:title="row.consent_message"
								:class="badgeClass(row.consent_warning)"
								>{{ row.consent_status }}</span
							>
							<span
								v-if="row.time_left"
								class="ml-2 text-sm text-ink"
								data-testid="sellos-queue-time-left"
								>{{ row.time_left }} left</span
							>
							<span
								v-else-if="row.consent_status === 'Consented'"
								class="ml-2 text-sm text-ink-muted"
								data-testid="sellos-queue-no-expiry"
								>No expiry</span
							>
						</div>
						<button
							type="button"
							class="btn"
							data-testid="sellos-queue-call"
							:aria-expanded="shown.has(row.lead)"
							@click="toggle(row.lead)"
						>
							Call
						</button>
					</div>
					<p
						v-if="row.consent_message"
						class="mt-2 text-sm"
						:class="row.consent_warning === 'red' ? 'text-accent' : 'text-ink-muted'"
						data-testid="sellos-queue-warning"
					>
						{{ row.consent_message }}
					</p>
					<p
						v-if="shown.has(row.lead)"
						class="mt-2 text-sm text-ink"
						data-testid="sellos-queue-number"
					>
						<template v-if="row.phone">
							<a
								v-if="view.full_numbers"
								:href="`tel:${row.phone}`"
								class="underline"
								>{{ row.phone }}</a
							>
							<span v-else>{{ row.phone }}</span>
							<span v-if="row.overseas_phone"> · {{ row.overseas_phone }}</span>
						</template>
						<template v-else>No phone</template>
					</p>
				</li>
			</ol>
		</template>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import { crmApi, serverMessage } from "../crm/crmApi";

// The caller queue (SOS-P2-09). The order and the time left come from the server. A red mark is an
// explicit stop request, amber is consent not established. Neither hides a lead or disables Call.
const view = ref(null);
const error = ref("");
const shown = reactive(new Set());

const badgeClass = (level) =>
	level === "red"
		? "border-accent text-accent"
		: level === "amber"
		? "border-line bg-brand-soft text-ink"
		: "border-line text-ink-muted";

function toggle(lead) {
	if (shown.has(lead)) shown.delete(lead);
	else shown.add(lead);
}

onMounted(async () => {
	try {
		view.value = await crmApi.callerQueue();
	} catch (e) {
		error.value = serverMessage(e, "The call queue could not be loaded.");
	}
});
</script>
