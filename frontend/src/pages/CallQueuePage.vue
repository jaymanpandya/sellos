<template>
	<PageTemplate shape="list" data-testid="sellos-queue">
		<template #header>
			<PageHeader title="Call queue" text="Who to call next." icon="lucide-phone" />
		</template>

		<template v-if="view" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-queue-stats" />
		</template>

		<Notice class="mb-ui-md" testid="sellos-queue-note">
			Consented leads come first, the soonest expiry first, then the rest. Every lead you may
			see is here, and a warning never stops a call.
		</Notice>
		<LoadError
			v-if="error"
			class="mb-ui-md"
			data-testid="sellos-queue-error"
			:message="error"
			@retry="load"
		/>

		<DataTable
			v-else
			title="Leads to call"
			caption="Call queue"
			:columns="columns"
			:rows="rows"
			row-key="lead"
			:loading="!view"
			loading-label="Loading the call queue."
			:row-to="rowTo"
			:row-name="(row) => row.lead_title"
			:row-attrs="rowAttrs"
			empty-title="No leads to call."
			empty-text="Leads you may see will be listed here."
			empty-icon="lucide-phone-off"
			testid="sellos-queue-list"
			row-testid="sellos-queue-row"
			loading-testid="sellos-queue-loading"
			empty-testid="sellos-queue-empty"
		>
			<template #cell-position="{ row }">
				<span class="ui-text-muted" data-testid="sellos-queue-position">{{
					row.position
				}}</span>
			</template>
			<template #cell-lead_title="{ row }">
				<span data-testid="sellos-queue-lead">{{ row.lead_title }}</span>
			</template>
			<template #cell-consent_status="{ row }">
				<StatusBadge
					:tone="toneOf(row.consent_warning)"
					:label="row.consent_status"
					data-testid="sellos-queue-consent"
					:data-level="row.consent_warning || 'none'"
					:title="row.consent_message"
				/>
				<p
					v-if="row.consent_message"
					class="mt-1 ui-text-small"
					:class="row.consent_warning === 'red' ? 'ui-text-error' : 'ui-text-muted'"
					data-testid="sellos-queue-warning"
				>
					{{ row.consent_message }}
				</p>
			</template>
			<template #cell-time_left="{ row }">
				<span
					v-if="row.time_left"
					class="ui-text-body"
					data-testid="sellos-queue-time-left"
					>{{ row.time_left }} left</span
				>
				<span
					v-else-if="row.consent_status === 'Consented'"
					class="ui-text-muted"
					data-testid="sellos-queue-no-expiry"
					>No expiry</span
				>
			</template>
			<template #cell-call="{ row }">
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-queue-call"
					:aria-expanded="shown.has(row.lead)"
					@click="toggle(row.lead)"
				>
					<template #prefix
						><span class="lucide-phone icon-inherit size-4" aria-hidden="true"
					/></template>
					Call
				</AppButton>
				<p
					v-if="shown.has(row.lead)"
					class="mt-ui-sm ui-text-small"
					data-testid="sellos-queue-number"
				>
					<template v-if="row.phone">
						<a v-if="view.full_numbers" :href="`tel:${row.phone}`" class="ui-link">{{
							row.phone
						}}</a>
						<span v-else>{{ row.phone }}</span>
						<span v-if="row.overseas_phone"> · {{ row.overseas_phone }}</span>
					</template>
					<template v-else>No phone</template>
				</p>
			</template>
		</DataTable>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import Notice from "../components/Notice.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { crmApi, serverMessage } from "../crm/crmApi";
import { setQueueCount } from "../navCounts";

// The caller queue (SOS-P2-09). The order and the time left come from the server. A red mark is an
// explicit stop request, amber is consent not established. Neither hides a lead or disables Call.
const view = ref(null);
const error = ref("");
const shown = reactive(new Set());

const rows = computed(() => view.value?.leads || []);
const toneOf = (level) => (level === "red" ? "danger" : level === "amber" ? "warning" : "neutral");

const columns = [
	{ key: "position", label: "#" },
	{ key: "lead_title", label: "Lead", primary: true },
	{ key: "stage", label: "Stage" },
	{ key: "consent_status", label: "Consent", wrap: true },
	{ key: "time_left", label: "Consent time left" },
	{ key: "call", label: "Call", wrap: true },
];

const kpis = computed(() => {
	const total = view.value?.total ?? 0;
	const warned = rows.value.filter((row) => row.consent_warning).length;
	const consented = rows.value.filter((row) => row.consent_status === "Consented").length;
	return [
		{
			label: total === 1 ? "Lead in the queue" : "Leads in the queue",
			value: total,
			caption: "Every lead you may see",
			icon: "lucide-phone",
			testid: "sellos-queue-count",
			valueTestid: "sellos-queue-count",
		},
		{
			label: "Consented",
			value: consented,
			caption: "Called first, soonest expiry first",
			icon: "lucide-shield-check",
			tone: "success",
		},
		{
			label: "With a warning",
			value: warned,
			caption: "A warning never stops a call",
			icon: "lucide-triangle-alert",
			tone: "warning",
		},
	];
});

const rowTo = (row) => `/crm/leads/${row.lead}`;
const rowAttrs = (row) => ({ "data-lead": row.lead, "data-status": row.consent_status });

function toggle(lead) {
	if (shown.has(lead)) shown.delete(lead);
	else shown.add(lead);
}

async function load() {
	error.value = "";
	try {
		view.value = await crmApi.callerQueue();
		setQueueCount(view.value.total);
	} catch (e) {
		error.value = serverMessage(e, "The call queue could not be loaded.");
	}
}

onMounted(load);
</script>
