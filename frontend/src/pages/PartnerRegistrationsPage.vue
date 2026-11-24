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

		<p
			v-if="error && !editingSettings"
			role="alert"
			data-testid="sellos-registrations-error"
			class="mb-ui-md text-sm text-accent"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-registrations-notice"
			class="mb-ui-md text-sm text-ink"
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
			:rows="rows"
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
				<span class="font-medium text-ink" data-testid="sellos-registrations-buyer">
					{{ r.buyer_name }}
				</span>
				<span
					class="block text-xs text-ink-muted"
					data-testid="sellos-registrations-phone"
				>
					{{ r.phone }}
				</span>
			</template>
			<template #cell-status="{ row: r }">
				<StatusBadge
					:tone="STATUS_TONE[r.status] || 'neutral'"
					:label="r.status"
					data-testid="sellos-registrations-status"
				/>
			</template>
			<template #cell-firm_name="{ row: r }">
				<p class="text-sm text-ink-muted">
					Registered by {{ r.firm_name }} ({{ r.partner_user }}).
					<span v-if="r.project_of_interest">Project: {{ r.project_of_interest }}.</span>
					<span data-testid="sellos-registrations-consent">
						Consent: {{ r.consent.status }}.
					</span>
				</p>
				<p v-if="r.note" class="text-sm text-ink-muted">{{ r.note }}</p>
				<p v-if="r.protected_until" class="text-sm text-ink-muted">
					<span v-if="r.protected">Protected until</span>
					<span v-else>Protection ended</span>
					{{ formatDate(r.protected_until) }}.
				</p>
				<p
					v-if="r.rejection_reason"
					class="text-sm text-ink-muted"
					data-testid="sellos-registrations-reason"
				>
					Rejected: {{ r.rejection_reason }}
				</p>
				<details class="mt-1" data-testid="sellos-registrations-log">
					<summary class="cursor-pointer text-sm text-ink-muted">Log</summary>
					<ul class="mt-1 space-y-1 text-sm text-ink-muted">
						<li
							v-for="(l, i) in r.log"
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
				</details>
			</template>
			<template #cell-actions="{ row: r }">
				<div
					v-if="r.status === 'Registered'"
					class="flex flex-wrap items-center gap-ui-sm"
				>
					<AppButton
						type="button"
						variant="primary"
						data-testid="sellos-registrations-approve"
						@click="act(() => api.approve(r.name), `${r.buyer_name} was approved.`)"
					>
						Approve
					</AppButton>
					<FormField
						v-model="reasons[r.name]"
						compact
						label="Reason for a rejection"
						data-testid="sellos-registrations-reason-input"
					/>
					<AppButton
						type="button"
						variant="danger"
						data-testid="sellos-registrations-reject"
						@click="reject(r)"
					>
						Reject
					</AppButton>
				</div>
			</template>
		</DataTable>

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
				class="text-sm text-accent"
			>
				{{ error }}
			</p>
		</FormDrawer>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
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
const reasons = reactive({});
const settings = reactive({
	partner_lead_limit: "",
	partner_protection_days: "",
	consent_wording: "",
	partner_confirmation_wording: "",
});

const columns = [
	{ key: "buyer_name", label: "Buyer", primary: true, sortable: true },
	{ key: "status", label: "Status", sortable: true },
	{ key: "firm_name", label: "Registered by", wrap: true },
	{ key: "actions", label: "Decision", wrap: true },
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

const reject = async (r) => {
	const done = await act(
		() => api.reject(r.name, reasons[r.name] || ""),
		`${r.buyer_name} was rejected.`,
		"The registration could not be rejected."
	);
	if (done) delete reasons[r.name];
};

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
