<template>
	<PageTemplate data-testid="sellos-partner-register-page">
		<template #header>
			<PageHeader
				title="Register a buyer"
				text="Register a buyer you brought. If the company does not already have them, the lead is protected in your firm's name once the company approves it."
				icon="lucide-user-plus"
			>
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-partner-register-new"
					@click="registering = true"
				>
					<template #prefix
						><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
					/></template>
					Register a buyer
				</AppButton>
			</PageHeader>
		</template>

		<template v-if="!loadError && loaded" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-partner-register-stats" />
		</template>

		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-partner-register-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<p
			v-if="error && !registering"
			role="alert"
			data-testid="sellos-partner-register-error"
			class="mb-ui-md text-sm text-accent"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-partner-register-notice"
			class="mb-ui-md text-sm text-ink"
		>
			{{ notice }}
		</p>

		<DataTable
			v-if="!loadError"
			title="Your registrations"
			:columns="columns"
			:rows="rows"
			:loading="!loaded"
			:row-attrs="(r) => ({ 'data-status': r.status })"
			empty-title="No registrations yet"
			empty-text="Register your first buyer with the button above."
			empty-icon="lucide-user-plus"
			testid="sellos-partner-register-list"
			row-testid="sellos-partner-register-row"
			empty-testid="sellos-partner-register-empty"
		>
			<template #cell-status="{ row: r }">
				<StatusBadge
					:tone="STATUS_TONE[r.status] || 'neutral'"
					:label="r.status"
					data-testid="sellos-partner-register-status"
				/>
			</template>
			<template #cell-protected_until="{ row: r }">
				<p v-if="r.protected_until" class="text-sm text-ink-muted">
					Protected in your firm's name until {{ formatDate(r.protected_until) }}.
				</p>
				<p
					v-if="r.rejection_reason"
					class="text-sm text-ink-muted"
					data-testid="sellos-partner-register-reason"
				>
					Rejected: {{ r.rejection_reason }}
				</p>
			</template>
		</DataTable>

		<FormDrawer
			:open="registering"
			title="Register a buyer"
			text="The buyer's phone is shown masked to you afterwards."
			submit-label="Register buyer"
			testid="sellos-partner-register-form"
			submit-testid="sellos-partner-register-submit"
			@close="registering = false"
			@submit="register"
		>
			<FormSection title="Buyer">
				<FormField
					v-model="form.buyer_name"
					label="Buyer's name"
					required
					data-testid="sellos-partner-register-name"
				/>
				<FormField
					v-model="form.phone"
					type="tel"
					label="Buyer's phone"
					required
					data-testid="sellos-partner-register-phone"
				/>
				<FormField
					v-model="form.email"
					type="email"
					label="Buyer's email (optional)"
					data-testid="sellos-partner-register-email"
				/>
				<FormField
					v-model="form.project_of_interest"
					label="Project of interest"
					data-testid="sellos-partner-register-project"
				/>
				<FormField
					v-model="form.note"
					type="textarea"
					label="Note"
					class="md:col-span-2"
					data-testid="sellos-partner-register-note"
				/>
			</FormSection>
			<FormSection title="Consent">
				<div class="space-y-ui-sm md:col-span-2">
					<p class="text-sm text-ink" data-testid="sellos-partner-register-wording">
						{{ wording }}
					</p>
					<FormField
						v-model="form.buyer_agreed"
						type="checkbox"
						label="The buyer agreed to this"
						data-testid="sellos-partner-register-agreed"
					/>
					<p class="text-sm text-ink-muted">
						You can register the buyer without it. The company then sees that consent
						is unknown.
					</p>
				</div>
			</FormSection>
			<p class="text-sm text-ink-muted" data-testid="sellos-partner-register-left">
				You can register {{ remaining }} more buyers this hour.
			</p>
			<p
				v-if="error"
				role="alert"
				data-testid="sellos-partner-register-error"
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
import { formatDate } from "../format";

// A partner registers a buyer (SOS-P7-02). The confirmation wording is the company's, shown as it will be kept.
// A buyer the company already has is answered with one sentence and nothing else.
const STATUS_TONE = {
	Registered: "info",
	Approved: "success",
	Visited: "success",
	Booked: "success",
	Expired: "neutral",
	Rejected: "danger",
};
const BLANK = {
	buyer_name: "",
	phone: "",
	email: "",
	project_of_interest: "",
	note: "",
	buyer_agreed: false,
};

const rows = ref([]);
const wording = ref("");
const remaining = ref(0);
const error = ref("");
const notice = ref("");
const loadError = ref("");
const loaded = ref(false);
const registering = ref(false);
const form = reactive({ ...BLANK });

const columns = [
	{ key: "buyer_name", label: "Buyer", primary: true, sortable: true },
	{ key: "phone_masked", label: "Phone" },
	{ key: "status", label: "Status", sortable: true },
	{ key: "protected_until", label: "Protection", wrap: true },
];

// Numbers the server already returned.
const kpis = computed(() => [
	{
		label: "Registrations",
		value: rows.value.length,
		caption: "Made by your firm",
		icon: "lucide-user-check",
	},
	{
		label: "Approved",
		value: rows.value.filter((r) => r.status === "Approved").length,
		caption: "Protected in your firm's name",
		icon: "lucide-badge-check",
		tone: "success",
	},
	{
		label: "Left this hour",
		value: remaining.value,
		caption: "Buyers you can still register",
		icon: "lucide-timer",
	},
]);

async function load() {
	loadError.value = "";
	try {
		const [info, mine] = await Promise.all([api.form(), api.mine()]);
		wording.value = info.confirmation_wording;
		remaining.value = info.remaining;
		rows.value = mine.registrations;
	} catch (e) {
		loadError.value = serverMessage(e, "The registrations could not be loaded.");
	} finally {
		loaded.value = true;
	}
}

async function register() {
	error.value = "";
	notice.value = "";
	try {
		const result = await api.register({ ...form, buyer_agreed: form.buyer_agreed ? 1 : 0 });
		if (result.accepted) {
			notice.value = `${result.registration.buyer_name} was registered. The company will approve it.`;
			Object.assign(form, BLANK);
			registering.value = false;
		} else {
			error.value = result.message;
		}
		await load();
	} catch (e) {
		error.value = serverMessage(e, "The buyer could not be registered.");
	}
}

onMounted(load);
</script>
