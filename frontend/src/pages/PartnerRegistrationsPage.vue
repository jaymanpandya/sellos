<template>
	<PageTemplate data-testid="sellos-registrations-page">
		<template #header>
			<PageHeader
				title="Partner registrations"
				text="Approve or reject each buyer a channel partner registered. An approved registration is protected in the partner's name, which decides who is owed commission. It never stops a call, a message or an agent's work."
				icon="lucide-user-check"
			>
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-registrations-settings-open"
					@click="editingSettings = true"
				>
					Partner settings
				</AppButton>
			</PageHeader>
		</template>

		<template v-if="!loadError" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-registrations-stats" />
		</template>

		<template #filters>
			<FilterBar
				v-model:search="search"
				search-label="Search registrations"
				search-placeholder="Search registrations"
				search-testid="sellos-registrations-search"
				clear-testid="sellos-registrations-filter-clear"
				:active="Boolean(search || statusFilter)"
				:chips="chips"
				data-testid="sellos-registrations-filters"
				@clear="clearFilters"
				@remove-chip="removeChip"
			>
				<FormField
					v-model="statusFilter"
					compact
					type="select"
					label="Status"
					:options="statusOptions"
					data-testid="sellos-registrations-filter-status"
				/>
			</FilterBar>
		</template>

		<p
			v-if="error && !editingSettings && !rejecting"
			role="alert"
			data-testid="sellos-registrations-error"
			class="mb-ui-md ui-text-error"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-registrations-notice"
			class="mb-ui-md ui-text-small"
		>
			{{ notice }}
		</p>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-registrations-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<DataTable
			v-else
			title="Registrations"
			:columns="columns"
			:rows="shown"
			:actions="rowActions"
			:loading="!loaded"
			:row-attrs="(r) => ({ 'data-status': r.status })"
			empty-title="No registrations yet"
			empty-text="A partner's registration appears here."
			empty-icon="lucide-user-check"
			testid="sellos-registrations-list"
			row-testid="sellos-registrations-row"
			empty-testid="sellos-registrations-empty"
		>
			<template #cell-buyer_name="{ row: r }">
				<NameCell
					:name="r.buyer_name"
					:identifier="r.phone"
					:detail="r.project_of_interest"
					data-testid="sellos-registrations-buyer"
				/>
			</template>
			<template #cell-status="{ row: r }">
				<StatusBadge
					:tone="STATUS_TONE[r.status] || 'neutral'"
					:label="r.status"
					data-testid="sellos-registrations-status"
				/>
			</template>
			<template #cell-firm_name="{ row: r }">
				<CellText :value="r.firm_name" />
				<CellText :value="r.partner_user" muted blank />
			</template>
			<template #cell-consent="{ row: r }">
				<CellText
					:value="`Consent: ${r.consent.status}`"
					data-testid="sellos-registrations-consent"
				/>
			</template>
			<template #cell-protection="{ row: r }">
				<CellText
					v-if="r.protected_until"
					:value="`${r.protected ? 'Protected until' : 'Protection ended'} ${formatDate(
						r.protected_until
					)}`"
					:lines="2"
				/>
			</template>
			<template #cell-note="{ row: r }">
				<CellText
					v-if="r.rejection_reason"
					:value="`Rejected: ${r.rejection_reason}`"
					:lines="2"
					muted
					data-testid="sellos-registrations-reason"
				/>
				<CellText v-else :value="r.note" :lines="2" muted blank />
			</template>
		</DataTable>

		<!-- Rejecting a registration needs a reason: a small drawer opened from the row menu. -->
		<FormDrawer
			:open="Boolean(rejecting)"
			:title="rejecting ? `Reject ${rejecting.buyer_name}` : 'Reject registration'"
			text="The partner sees the reason."
			submit-label="Reject"
			testid="sellos-registrations-reject-drawer"
			submit-testid="sellos-registrations-reject"
			@close="closeReject"
			@submit="reject"
		>
			<FormSection title="Reason">
				<FormField
					v-model="reason"
					label="Reason for a rejection"
					class="md:col-span-2"
					data-testid="sellos-registrations-reason-input"
				/>
			</FormSection>
			<p
				v-if="error"
				role="alert"
				data-testid="sellos-registrations-error"
				class="ui-text-error"
			>
				{{ error }}
			</p>
		</FormDrawer>

		<!-- The log of one registration: read only, opened from the row menu. -->
		<FormDrawer
			:open="Boolean(viewing)"
			:title="viewing ? `${viewing.buyer_name}: log` : 'Log'"
			submit-label="Close"
			testid="sellos-registrations-log-drawer"
			submit-testid="sellos-registrations-log-close"
			@close="viewing = null"
			@submit="viewing = null"
		>
			<FormSection v-if="viewing" title="Log">
				<ul
					class="space-y-1 ui-text-muted md:col-span-2"
					data-testid="sellos-registrations-log"
				>
					<li
						v-for="(l, i) in viewing.log"
						:key="i"
						data-testid="sellos-registrations-log-row"
					>
						{{ formatWhen(l.changed_on) }}: {{ l.changed_by }}
						<span v-if="l.from_status !== l.to_status">
							moved it
							<span v-if="l.from_status">from {{ l.from_status }}</span>
							to {{ l.to_status }}
						</span>
						<span v-if="l.note"> ({{ l.note }})</span>
					</li>
				</ul>
			</FormSection>
		</FormDrawer>

		<!-- The programme's settings are a drawer, not a form under the list. -->
		<FormDrawer
			:open="editingSettings"
			title="Partner settings"
			text="Limits and wording for the channel partner programme."
			submit-label="Save settings"
			testid="sellos-registrations-settings"
			submit-testid="sellos-registrations-save-settings"
			@close="editingSettings = false"
			@submit="saveSettings"
		>
			<FormSection title="Limits">
				<FormField
					v-model="settings.partner_lead_limit"
					type="number"
					label="Partner lead limit (leads per partner per hour)"
					data-testid="sellos-registrations-limit"
				/>
				<FormField
					v-model="settings.partner_protection_days"
					type="number"
					label="Partner protection days"
					data-testid="sellos-registrations-days"
				/>
			</FormSection>
			<FormSection title="Wording">
				<FormField
					v-model="settings.consent_wording"
					type="textarea"
					label="Consent wording"
					hint="Shown to a buyer on the enquiry page and the website forms."
					class="md:col-span-2"
					data-testid="sellos-registrations-wording"
				/>
				<FormField
					v-model="settings.partner_confirmation_wording"
					type="textarea"
					label="Partner confirmation wording"
					hint="Shown to the partner when they confirm the buyer agreed."
					class="md:col-span-2"
					data-testid="sellos-registrations-confirmation"
				/>
			</FormSection>
			<p
				v-if="error"
				role="alert"
				data-testid="sellos-registrations-error"
				class="ui-text-error"
			>
				{{ error }}
			</p>
		</FormDrawer>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import CellText from "../components/CellText.vue";
import NameCell from "../components/NameCell.vue";
import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import FilterBar from "../components/FilterBar.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { partnerRegistrationsApi as api } from "../company/partnerRegistrationsApi";
import { serverMessage } from "../crm/crmApi";
import { formatDate, formatWhen } from "../format";

// The Company Admin decides each partner registration (SOS-P7-02) and sets the programme's company settings.
const STATUS_TONE = {
	Registered: "info",
	Approved: "success",
	Visited: "success",
	Booked: "success",
	Expired: "neutral",
	Rejected: "danger",
};

const rows = ref([]);
const counts = ref({});
const error = ref("");
const notice = ref("");
const loadError = ref("");
const loaded = ref(false);
const editingSettings = ref(false);
const rejecting = ref(null);
const viewing = ref(null);
const reason = ref("");
const settings = reactive({
	partner_lead_limit: "",
	partner_protection_days: "",
	consent_wording: "",
	partner_confirmation_wording: "",
});

const search = ref("");
const statusFilter = ref("");
const statusOptions = computed(() => [
	{ label: "All", value: "" },
	...[...new Set(rows.value.map((r) => r.status).filter(Boolean))].map((v) => ({
		label: v,
		value: v,
	})),
]);
const shown = computed(() => {
	const q = search.value.trim().toLowerCase();
	return rows.value.filter(
		(r) =>
			(!q || `${r.buyer_name} ${r.firm_name || ""}`.toLowerCase().includes(q)) &&
			(!statusFilter.value || r.status === statusFilter.value)
	);
});
const chips = computed(() => [
	...(search.value ? [{ key: "search", label: `Search: ${search.value}` }] : []),
	...(statusFilter.value ? [{ key: "status", label: statusFilter.value }] : []),
]);
function clearFilters() {
	search.value = "";
	statusFilter.value = "";
}
function removeChip(key) {
	if (key === "search") search.value = "";
	else statusFilter.value = "";
}

const columns = [
	{ key: "buyer_name", label: "Buyer", primary: true, sortable: true },
	{ key: "status", label: "Status", sortable: true },
	{ key: "firm_name", label: "Registered by" },
	{ key: "consent", label: "Consent" },
	{ key: "protection", label: "Protection" },
	{ key: "note", label: "Note" },
];

// Four cards at most: the stages a registration passes through. Expired and Rejected stay in the table.
const kpis = computed(() => [
	{
		label: "Registered",
		value: counts.value["Registered"] || 0,
		caption: "Waiting for you",
		icon: "lucide-user-check",
		tone: "warning",
	},
	{
		label: "Approved",
		value: counts.value["Approved"] || 0,
		caption: "Protected in the partner's name",
		icon: "lucide-badge-check",
		tone: "success",
	},
	{
		label: "Visited",
		value: counts.value["Visited"] || 0,
		caption: "Came to a site visit",
		icon: "lucide-map-pin",
	},
	{
		label: "Booked",
		value: counts.value["Booked"] || 0,
		caption: "Became a booking",
		icon: "lucide-handshake",
		tone: "success",
	},
]);

function show(data) {
	rows.value = data.registrations;
	counts.value = data.counts;
}

async function load() {
	loadError.value = "";
	try {
		const [list, saved] = await Promise.all([api.list(), api.settings()]);
		show(list);
		Object.assign(settings, saved);
	} catch (e) {
		loadError.value = serverMessage(e, "The registrations could not be loaded.");
	} finally {
		loaded.value = true;
	}
}

async function act(action, message, fallback = "The change could not be made.") {
	error.value = "";
	notice.value = "";
	try {
		show(await action());
		notice.value = message;
		return true;
	} catch (e) {
		error.value = serverMessage(e, fallback);
		return false;
	}
}

function openReject(r) {
	error.value = "";
	notice.value = "";
	reason.value = "";
	rejecting.value = r;
}
function closeReject() {
	rejecting.value = null;
	error.value = "";
}

const reject = async () => {
	const r = rejecting.value;
	if (!r) return;
	const done = await act(
		() => api.reject(r.name, reason.value || ""),
		`${r.buyer_name} was rejected.`,
		"The registration could not be rejected."
	);
	if (done) rejecting.value = null;
};

// Every row action is in the row menu (docs/DESIGN_SYSTEM.md, "Lists", rule c).
const rowActions = (r) => [
	...(r.status === "Registered"
		? [
				{
					label: "Approve",
					onClick: () => act(() => api.approve(r.name), `${r.buyer_name} was approved.`),
				},
				{ label: "Reject", onClick: () => openReject(r) },
		  ]
		: []),
	{ label: "Log", onClick: () => (viewing.value = r) },
];

async function saveSettings() {
	error.value = "";
	notice.value = "";
	try {
		Object.assign(settings, await api.saveSettings({ ...settings }));
		notice.value = "The settings were saved.";
		editingSettings.value = false;
	} catch (e) {
		error.value = serverMessage(e, "The settings could not be saved.");
	}
}

onMounted(load);
</script>
