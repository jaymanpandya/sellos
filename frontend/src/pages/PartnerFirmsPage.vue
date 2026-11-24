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

		<p
			v-if="error && !inviting"
			role="alert"
			data-testid="sellos-partners-error"
			class="mb-ui-md text-sm text-accent"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-partners-notice"
			class="mb-ui-md text-sm text-ink"
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
			:rows="firms"
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
				<span class="font-medium text-ink" data-testid="sellos-partners-firm-name">
					{{ f.firm_name }}
				</span>
				<span class="block text-xs text-ink-muted" data-testid="sellos-partners-code">
					{{ f.partner_code }}
				</span>
			</template>
			<template #cell-status="{ row: f }">
				<StatusBadge
					:tone="STATUS_TONE[f.status] || 'neutral'"
					:label="f.status"
					data-testid="sellos-partners-status"
				/>
			</template>
			<template #cell-contact_person="{ row: f }">
				<span class="block text-ink">{{ f.contact_person }}</span>
				<span class="block text-xs text-ink-muted">
					{{ f.email }}
					<span v-if="f.phone" data-testid="sellos-partners-phone">, {{ f.phone }}</span>
				</span>
			</template>
			<template #cell-details="{ row: f }">
				<p class="text-sm text-ink-muted">
					RERA: {{ f.rera_number || "not given" }}. PAN:
					<span data-testid="sellos-partners-pan">{{ f.pan || "not given" }}</span
					>.
					<a
						v-if="f.agreement"
						:href="f.agreement"
						target="_blank"
						rel="noopener"
						class="text-accent underline"
						data-testid="sellos-partners-agreement"
					>
						Signed agreement
					</a>
					<span v-else data-testid="sellos-partners-no-agreement">
						No signed agreement yet.
					</span>
				</p>
				<p
					v-if="f.status === 'Suspended' && f.status_reason"
					class="text-sm text-ink-muted"
					data-testid="sellos-partners-reason"
				>
					Suspended: {{ f.status_reason }}
				</p>
				<p
					v-if="f.status === 'Pending approval' && f.missing.length"
					class="text-sm text-ink-muted"
				>
					Still missing: {{ f.missing.join(", ") }}.
				</p>
				<details class="mt-1" data-testid="sellos-partners-log">
					<summary class="cursor-pointer text-sm text-ink-muted">Status log</summary>
					<ul class="mt-1 space-y-1 text-sm text-ink-muted">
						<li v-for="(l, i) in f.log" :key="i" data-testid="sellos-partners-log-row">
							{{ formatWhen(l.changed_on) }}: {{ l.changed_by_name }} moved it
							<span v-if="l.from_status">from {{ l.from_status }}</span>
							to {{ l.to_status }}<span v-if="l.reason"> ({{ l.reason }})</span>
						</li>
					</ul>
				</details>
			</template>
			<template #cell-actions="{ row: f }">
				<div class="flex flex-wrap items-center gap-ui-sm">
					<AppButton
						v-if="f.status === 'Pending approval'"
						type="button"
						variant="primary"
						data-testid="sellos-partners-approve"
						@click="act(() => partnersApi.approve(f.name), 'The firm was approved.')"
					>
						Approve
					</AppButton>
					<AppButton
						v-if="f.status === 'Suspended'"
						type="button"
						data-testid="sellos-partners-reinstate"
						@click="
							act(() => partnersApi.reinstate(f.name), 'The firm was reinstated.')
						"
					>
						Reinstate
					</AppButton>
					<template v-if="f.status !== 'Suspended'">
						<FormField
							v-model="reasons[f.name]"
							compact
							label="Reason for a suspension"
							data-testid="sellos-partners-reason-input"
						/>
						<AppButton
							type="button"
							variant="danger"
							data-testid="sellos-partners-suspend"
							@click="suspend(f)"
						>
							Suspend
						</AppButton>
					</template>
				</div>
			</template>
		</DataTable>

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
			<p
				v-if="error"
				role="alert"
				data-testid="sellos-partners-error"
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
const reasons = reactive({});
const form = reactive({ firm_name: "", contact_person: "", email: "", phone: "" });

const columns = [
	{ key: "firm_name", label: "Firm", primary: true, sortable: true },
	{ key: "status", label: "Status", sortable: true },
	{ key: "contact_person", label: "Contact", wrap: true },
	{ key: "details", label: "Details", wrap: true },
	{ key: "actions", label: "Actions", wrap: true },
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

const suspend = async (firm) => {
	const done = await act(
		() => partnersApi.suspend(firm.name, reasons[firm.name] || ""),
		`${firm.firm_name} was suspended.`,
		"The firm could not be suspended."
	);
	if (done) delete reasons[firm.name];
};

onMounted(load);
</script>
