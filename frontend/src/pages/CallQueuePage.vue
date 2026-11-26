<template>
	<PageTemplate shape="list" data-testid="sellos-queue">
		<template #header>
			<PageHeader title="Call queue" text="Who to call next." icon="lucide-phone" />
		</template>

		<template v-if="view" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-queue-stats" />
		</template>

		<template v-if="view" #filters>
			<FilterBar
				v-model:search="search"
				search-label="Search the call queue"
				search-placeholder="Search by lead"
				search-testid="sellos-queue-search"
				clear-testid="sellos-queue-filter-clear"
				:active="Boolean(search || stageFilter || consentFilter || warningFilter)"
				:chips="chips"
				data-testid="sellos-queue-filters"
				@clear="clearFilters"
				@remove-chip="removeChip"
			>
				<FormField
					v-model="stageFilter"
					compact
					type="select"
					label="Stage"
					:options="stageOptions"
					data-testid="sellos-queue-filter-stage"
				/>
				<FormField
					v-model="consentFilter"
					compact
					type="select"
					label="Consent"
					:options="consentOptions"
					data-testid="sellos-queue-filter-consent"
				/>
				<FormField
					v-model="warningFilter"
					compact
					type="select"
					label="Warning"
					:options="warningOptions"
					data-testid="sellos-queue-filter-warning"
				/>
			</FilterBar>
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
			dense
			:rows="shownRows"
			:actions="rowActions"
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
				<NameCell
					:name="row.lead_name || row.lead_title"
					:identifier="row.phone"
					data-testid="sellos-queue-lead"
				/>
			</template>
			<template #cell-source="{ row }">
				<CellText :value="row.lead_source" />
			</template>
			<template #cell-stage="{ row }">
				<CellText :value="row.stage" />
			</template>
			<template #cell-consent_status="{ row }">
				<StatusBadge
					:tone="toneOf(row.consent_warning)"
					:label="row.consent_status"
					data-testid="sellos-queue-consent"
					:data-level="row.consent_warning || 'none'"
					:title="row.consent_message"
				/>
				<CellText
					v-if="row.consent_message"
					:value="row.consent_message"
					:class="row.consent_warning === 'red' ? 'ui-text-error' : 'ui-text-muted'"
					data-testid="sellos-queue-warning"
				/>
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
		</DataTable>

		<!-- Calling a lead: the number to dial, from the row menu. A warning never stops a call. -->
		<FormDrawer
			:open="Boolean(calling)"
			:title="calling ? `Call ${calling.lead_name || calling.lead_title}` : 'Call'"
			text="The number to dial. A consent warning never stops a call."
			submit-label="Done"
			testid="sellos-queue-call-drawer"
			submit-testid="sellos-queue-call-done"
			@close="calling = null"
			@submit="calling = null"
		>
			<p v-if="calling" class="ui-text-body" data-testid="sellos-queue-number">
				<template v-if="calling.phone">
					<a v-if="view.full_numbers" :href="`tel:${calling.phone}`" class="ui-link">{{
						calling.phone
					}}</a>
					<span v-else>{{ calling.phone }}</span>
					<span v-if="calling.overseas_phone"> · {{ calling.overseas_phone }}</span>
				</template>
				<template v-else>No phone</template>
			</p>
		</FormDrawer>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import CellText from "../components/CellText.vue";
import DataTable from "../components/DataTable.vue";
import FilterBar from "../components/FilterBar.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import NameCell from "../components/NameCell.vue";
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
const calling = ref(null);

const rows = computed(() => view.value?.leads || []);
const router = useRouter();
const search = ref("");
const stageFilter = ref("");
const consentFilter = ref("");
const warningFilter = ref("");
const options = (label, values) => [
	{ label, value: "" },
	...[...new Set(values.filter(Boolean))].sort().map((v) => ({ label: v, value: v })),
];
const stageOptions = computed(() =>
	options(
		"Any stage",
		rows.value.map((r) => r.stage)
	)
);
const consentOptions = computed(() =>
	options(
		"Any consent",
		rows.value.map((r) => r.consent_status)
	)
);
const warningOptions = [
	{ label: "Any", value: "" },
	{ label: "With a warning", value: "yes" },
	{ label: "No warning", value: "no" },
];
const shownRows = computed(() => {
	const q = search.value.trim().toLowerCase();
	return rows.value.filter(
		(r) =>
			(!q || `${r.lead_name || ""} ${r.lead_title || ""}`.toLowerCase().includes(q)) &&
			(!stageFilter.value || r.stage === stageFilter.value) &&
			(!consentFilter.value || r.consent_status === consentFilter.value) &&
			(!warningFilter.value ||
				(warningFilter.value === "yes") === Boolean(r.consent_warning))
	);
});
const chips = computed(() => [
	...(search.value ? [{ key: "search", label: `Lead: ${search.value}` }] : []),
	...(stageFilter.value ? [{ key: "stage", label: `Stage: ${stageFilter.value}` }] : []),
	...(consentFilter.value ? [{ key: "consent", label: `Consent: ${consentFilter.value}` }] : []),
	...(warningFilter.value
		? [
				{
					key: "warning",
					label: warningFilter.value === "yes" ? "With a warning" : "No warning",
				},
		  ]
		: []),
]);
function clearFilters() {
	search.value = stageFilter.value = consentFilter.value = warningFilter.value = "";
}
function removeChip(key) {
	const refs = { search, stage: stageFilter, consent: consentFilter, warning: warningFilter };
	refs[key].value = "";
}
const rowActions = (row) => [
	{ label: "Call", onClick: () => (calling.value = row) },
	{ label: "Open lead", onClick: () => router.push(`/crm/leads/${row.lead}`) },
];
const toneOf = (level) => (level === "red" ? "danger" : level === "amber" ? "warning" : "neutral");

const columns = [
	{ key: "position", label: "#" },
	{ key: "lead_title", label: "Lead", primary: true },
	{ key: "source", label: "Source" },
	{ key: "stage", label: "Stage" },
	{ key: "consent_status", label: "Consent", wrap: true },
	{ key: "time_left", label: "Consent time left" },
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
