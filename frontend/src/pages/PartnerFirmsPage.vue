<template>
	<PageTemplate data-testid="sellos-partners-page">
		<template #header>
			<PageHeader
				title="Channel partners"
				text="Invite a partner firm by email. Its contact person signs in, completes the firm's details, and the firm waits here for your approval. Only an approved firm may register leads."
				icon="lucide-handshake"
			>
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-partners-new"
					@click="inviting = true"
				>
					<template #prefix
						><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
					/></template>
					Invite a firm
				</AppButton>
			</PageHeader>
		</template>

		<template v-if="!loadError" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-partners-stats" />
		</template>

		<template #filters>
			<FilterBar
				v-model:search="search"
				search-label="Search firms"
				search-placeholder="Search firms"
				search-testid="sellos-partners-search"
				clear-testid="sellos-partners-filter-clear"
				:active="Boolean(search || statusFilter)"
				:chips="chips"
				data-testid="sellos-partners-filters"
				@clear="clearFilters"
				@remove-chip="removeChip"
			>
				<FormField
					v-model="statusFilter"
					compact
					type="select"
					label="Status"
					:options="statusOptions"
					data-testid="sellos-partners-filter-status"
				/>
			</FilterBar>
		</template>

		<p
			v-if="error && !inviting && !suspending"
			role="alert"
			data-testid="sellos-partners-error"
			class="mb-ui-md ui-text-error"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-partners-notice"
			class="mb-ui-md ui-text-small"
		>
			{{ notice }}
		</p>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-partners-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<DataTable
			v-else
			title="Partner firms"
			:columns="columns"
			:rows="shown"
			:actions="rowActions"
			:loading="!loaded"
			:row-attrs="(f) => ({ 'data-status': f.status })"
			empty-title="No partner firms yet"
			empty-text="Invite the first firm with the button above."
			empty-icon="lucide-handshake"
			testid="sellos-partners-list"
			row-testid="sellos-partners-row"
			empty-testid="sellos-partners-empty"
		>
			<template #cell-firm_name="{ row: f }">
				<NameCell
					:name="f.firm_name"
					:identifier="f.partner_code"
					:detail="f.email"
					data-testid="sellos-partners-firm-name"
				/>
			</template>
			<template #cell-status="{ row: f }">
				<StatusBadge
					:tone="STATUS_TONE[f.status] || 'neutral'"
					:label="f.status"
					data-testid="sellos-partners-status"
				/>
			</template>
			<template #cell-contact_person="{ row: f }">
				<CellText :value="f.contact_person" />
				<CellText :value="f.phone" muted blank data-testid="sellos-partners-phone" />
			</template>
			<template #cell-rera="{ row: f }">
				<CellText :value="f.rera_number" />
			</template>
			<template #cell-pan="{ row: f }">
				<CellText :value="f.pan" data-testid="sellos-partners-pan" />
			</template>
			<template #cell-agreement="{ row: f }">
				<span v-if="f.agreement" class="block" data-testid="sellos-partners-has-agreement"
					>Signed</span
				>
				<span v-else class="block ui-text-muted" data-testid="sellos-partners-no-agreement"
					>Not signed yet</span
				>
			</template>
			<template #cell-note="{ row: f }">
				<CellText
					v-if="f.status === 'Suspended' && f.status_reason"
					:value="`Suspended: ${f.status_reason}`"
					:lines="2"
					muted
					data-testid="sellos-partners-reason"
				/>
				<CellText
					v-else-if="f.status === 'Pending approval' && f.missing.length"
					:value="`Still missing: ${f.missing.join(', ')}`"
					:lines="2"
					muted
				/>
			</template>
		</DataTable>

		<!-- Suspending a firm needs a reason: a small drawer opened from the row menu. -->
		<FormDrawer
			:open="Boolean(suspending)"
			:title="suspending ? `Suspend ${suspending.firm_name}` : 'Suspend firm'"
			text="The firm may not register leads until you reinstate it. The reason is kept on the firm."
			submit-label="Suspend"
			testid="sellos-partners-suspend-drawer"
			submit-testid="sellos-partners-suspend"
			@close="closeSuspend"
			@submit="suspend"
		>
			<FormSection title="Reason">
				<FormField
					v-model="reason"
					label="Reason for a suspension"
					class="md:col-span-2"
					data-testid="sellos-partners-reason-input"
				/>
			</FormSection>
			<p v-if="error" role="alert" data-testid="sellos-partners-error" class="ui-text-error">
				{{ error }}
			</p>
		</FormDrawer>

		<!-- The signed agreement and the status log of one firm: read only, opened from the row menu. -->
		<FormDrawer
			:open="Boolean(viewing)"
			:title="viewing ? `${viewing.firm_name}: agreement and status log` : 'Agreement'"
			submit-label="Close"
			testid="sellos-partners-history-drawer"
			submit-testid="sellos-partners-history-close"
			@close="viewing = null"
			@submit="viewing = null"
		>
			<template v-if="viewing">
				<FormSection title="Agreement">
					<a
						v-if="viewing.agreement"
						:href="viewing.agreement"
						target="_blank"
						rel="noopener"
						class="underline ui-text-error md:col-span-2"
						data-testid="sellos-partners-agreement"
					>
						Signed agreement
					</a>
					<p v-else class="ui-text-muted md:col-span-2">No signed agreement yet.</p>
				</FormSection>
				<FormSection title="Status log">
					<ul
						class="space-y-1 ui-text-muted md:col-span-2"
						data-testid="sellos-partners-log"
					>
						<li
							v-for="(l, i) in viewing.log"
							:key="i"
							data-testid="sellos-partners-log-row"
						>
							{{ formatWhen(l.changed_on) }}: {{ l.changed_by_name }} moved it
							<span v-if="l.from_status">from {{ l.from_status }}</span>
							to {{ l.to_status }}<span v-if="l.reason"> ({{ l.reason }})</span>
						</li>
					</ul>
				</FormSection>
			</template>
		</FormDrawer>

		<!-- Inviting a firm is a drawer, not a form under the list. -->
		<FormDrawer
			:open="inviting"
			title="Invite a partner firm"
			text="Its contact person gets an email to set a password."
			submit-label="Invite firm"
			testid="sellos-partners-form"
			submit-testid="sellos-partners-invite"
			@close="inviting = false"
			@submit="invite"
		>
			<FormSection title="Firm">
				<FormField
					v-model="form.firm_name"
					label="Firm name"
					required
					class="md:col-span-2"
					data-testid="sellos-partners-firm"
				/>
			</FormSection>
			<FormSection title="Contact person">
				<FormField
					v-model="form.contact_person"
					label="Contact person"
					required
					data-testid="sellos-partners-contact"
				/>
				<FormField
					v-model="form.email"
					type="email"
					label="Contact email"
					required
					data-testid="sellos-partners-email"
				/>
				<FormField
					v-model="form.phone"
					type="tel"
					label="Phone (optional)"
					hint="The contact person can give it later."
					data-testid="sellos-partners-phone-input"
				/>
			</FormSection>
			<p v-if="error" role="alert" data-testid="sellos-partners-error" class="ui-text-error">
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
import { partnersApi } from "../company/partnersApi";
import { serverMessage } from "../crm/crmApi";
import { formatWhen } from "../format";

// The Company Admin's channel partner firms (SOS-P7-01). Every change is made on the server and the list
// read back, so what is shown is what is saved.
const STATUS_TONE = {
	Invited: "info",
	"Pending approval": "warning",
	Approved: "success",
	Suspended: "danger",
};

const firms = ref([]);
const counts = ref({});
const error = ref("");
const notice = ref("");
const loadError = ref("");
const loaded = ref(false);
const inviting = ref(false);
const suspending = ref(null);
const viewing = ref(null);
const reason = ref("");
const form = reactive({ firm_name: "", contact_person: "", email: "", phone: "" });

const search = ref("");
const statusFilter = ref("");
const statusOptions = computed(() => [
	{ label: "All", value: "" },
	...[...new Set(firms.value.map((r) => r.status).filter(Boolean))].map((v) => ({
		label: v,
		value: v,
	})),
]);
const shown = computed(() => {
	const q = search.value.trim().toLowerCase();
	return firms.value.filter(
		(r) =>
			(!q || `${r.firm_name} ${r.contact_person || ""}`.toLowerCase().includes(q)) &&
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
	{ key: "firm_name", label: "Firm", primary: true, sortable: true },
	{ key: "status", label: "Status", sortable: true },
	{ key: "contact_person", label: "Contact" },
	{ key: "rera", label: "RERA" },
	{ key: "pan", label: "PAN" },
	{ key: "agreement", label: "Agreement" },
	{ key: "note", label: "Note" },
];

const kpis = computed(() => [
	{
		label: "Invited",
		value: counts.value["Invited"] || 0,
		caption: "Waiting to sign in",
		icon: "lucide-mail",
	},
	{
		label: "Pending approval",
		value: counts.value["Pending approval"] || 0,
		caption: "Waiting for you",
		icon: "lucide-clock",
		tone: "warning",
	},
	{
		label: "Approved",
		value: counts.value["Approved"] || 0,
		caption: "May register leads",
		icon: "lucide-badge-check",
		tone: "success",
	},
	{
		label: "Suspended",
		value: counts.value["Suspended"] || 0,
		caption: "May not register leads",
		icon: "lucide-ban",
		tone: "danger",
	},
]);

function show(data) {
	firms.value = data.firms;
	counts.value = data.counts;
}

async function load() {
	loadError.value = "";
	try {
		show(await partnersApi.list());
	} catch (e) {
		loadError.value = serverMessage(e, "The partner firms could not be loaded.");
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

const invite = async () => {
	const values = { ...form };
	const done = await act(
		() => partnersApi.invite(values),
		`${values.firm_name} was invited. Its contact person gets an email to set a password, or the invitation is saved if this site can not send mail yet.`,
		"The firm could not be invited."
	);
	if (done) {
		Object.assign(form, { firm_name: "", contact_person: "", email: "", phone: "" });
		inviting.value = false;
	}
};

function openSuspend(firm) {
	error.value = "";
	notice.value = "";
	reason.value = "";
	suspending.value = firm;
}
function closeSuspend() {
	suspending.value = null;
	error.value = "";
}

const suspend = async () => {
	const firm = suspending.value;
	if (!firm) return;
	const done = await act(
		() => partnersApi.suspend(firm.name, reason.value || ""),
		`${firm.firm_name} was suspended.`,
		"The firm could not be suspended."
	);
	if (done) suspending.value = null;
};

// Every row action is in the row menu (docs/DESIGN_SYSTEM.md, "Lists", rule c).
const rowActions = (f) => [
	...(f.status === "Pending approval"
		? [
				{
					label: "Approve",
					onClick: () =>
						act(() => partnersApi.approve(f.name), "The firm was approved."),
				},
		  ]
		: []),
	...(f.status === "Suspended"
		? [
				{
					label: "Reinstate",
					onClick: () =>
						act(() => partnersApi.reinstate(f.name), "The firm was reinstated."),
				},
		  ]
		: [{ label: "Suspend", onClick: () => openSuspend(f) }]),
	{ label: "Agreement and status log", onClick: () => (viewing.value = f) },
];

onMounted(load);
</script>
