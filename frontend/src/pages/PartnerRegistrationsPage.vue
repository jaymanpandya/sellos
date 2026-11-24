<template>
	<div data-testid="sellos-registrations-page">
		<PageHeader
			title="Partner registrations"
			text="Approve or reject each buyer a channel partner registered. An approved registration is protected in the partner's name, which decides who is owed commission. It never stops a call, a message or an agent's work."
			icon="lucide-user-check"
		/>
		<p
			v-if="error"
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

		<div
			class="mb-ui-md grid grid-cols-2 gap-ui-md md:grid-cols-3 lg:grid-cols-6"
			data-testid="sellos-registrations-stats"
		>
			<StatCard
				v-for="status in STATUSES"
				:key="status"
				:label="status"
				:value="counts[status] || 0"
				icon="lucide-user-check"
			/>
		</div>

		<ListCard title="Registrations">
			<EmptyState
				v-if="loaded && !loadError && !rows.length"
				title="No registrations yet"
				text="A partner's registration appears here."
				icon="lucide-user-check"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-registrations-list">
				<li
					v-for="r in rows"
					:key="r.name"
					data-testid="sellos-registrations-row"
					:data-name="r.name"
					:data-status="r.status"
					class="rounded-input border border-line-soft p-ui-md"
				>
					<div class="flex flex-wrap items-center gap-3">
						<span
							class="font-medium text-ink"
							data-testid="sellos-registrations-buyer"
						>
							{{ r.buyer_name }}
						</span>
						<span
							class="text-sm text-ink-muted"
							data-testid="sellos-registrations-phone"
						>
							{{ r.phone }}
						</span>
						<StatusBadge
							:tone="STATUS_TONE[r.status] || 'neutral'"
							:label="r.status"
							data-testid="sellos-registrations-status"
						/>
					</div>
					<p class="mt-1 text-sm text-ink-muted">
						Registered by {{ r.firm_name }} ({{ r.partner_user }}).
						<span v-if="r.project_of_interest">
							Project: {{ r.project_of_interest }}.
						</span>
						<span data-testid="sellos-registrations-consent">
							Consent: {{ r.consent.status }}.
						</span>
					</p>
					<p v-if="r.note" class="text-sm text-ink-muted">{{ r.note }}</p>
					<p v-if="r.protected_until" class="text-sm text-ink-muted">
						<span v-if="r.protected">Protected until</span>
						<span v-else>Protection ended</span>
						{{ r.protected_until }}.
					</p>
					<p
						v-if="r.rejection_reason"
						class="text-sm text-ink-muted"
						data-testid="sellos-registrations-reason"
					>
						Rejected: {{ r.rejection_reason }}
					</p>

					<div
						v-if="r.status === 'Registered'"
						class="mt-ui-sm flex flex-wrap items-end gap-ui-sm"
					>
						<AppButton
							type="button"
							variant="primary"
							data-testid="sellos-registrations-approve"
							@click="
								act(() => api.approve(r.name), `${r.buyer_name} was approved.`)
							"
						>
							Approve
						</AppButton>
						<FormField
							v-model="reasons[r.name]"
							label="Reason for a rejection"
							class="w-72"
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

					<details class="mt-ui-sm" data-testid="sellos-registrations-log">
						<summary class="cursor-pointer text-sm text-ink-muted">Log</summary>
						<ul class="mt-1 space-y-1 text-sm text-ink-muted">
							<li
								v-for="(l, i) in r.log"
								:key="i"
								data-testid="sellos-registrations-log-row"
							>
								{{ l.changed_on }}: {{ l.changed_by }}
								<span v-if="l.from_status !== l.to_status">
									moved it
									<span v-if="l.from_status">from {{ l.from_status }}</span>
									to {{ l.to_status }}
								</span>
								<span v-if="l.note"> ({{ l.note }})</span>
							</li>
						</ul>
					</details>
				</li>
			</ul>
		</ListCard>

		<form
			class="ui-card mt-ui-md"
			data-testid="sellos-registrations-settings"
			@submit.prevent="saveSettings"
		>
			<h2 class="ui-card-heading mb-ui-md">Partner settings</h2>
			<div class="grid grid-cols-1 gap-x-ui-md gap-y-ui-md md:grid-cols-2">
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
				<FormField
					v-model="settings.consent_wording"
					type="textarea"
					label="Consent wording"
					hint="Shown to a buyer on the enquiry page and the website forms."
					data-testid="sellos-registrations-wording"
				/>
				<FormField
					v-model="settings.partner_confirmation_wording"
					type="textarea"
					label="Partner confirmation wording"
					hint="Shown to the partner when they confirm the buyer agreed."
					data-testid="sellos-registrations-confirmation"
				/>
			</div>
			<div class="mt-ui-md">
				<AppButton
					type="submit"
					variant="primary"
					data-testid="sellos-registrations-save-settings"
				>
					Save settings
				</AppButton>
			</div>
		</form>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import StatCard from "../components/StatCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { partnerRegistrationsApi as api } from "../company/partnerRegistrationsApi";
import { serverMessage } from "../crm/crmApi";

// The Company Admin decides each partner registration (SOS-P7-02) and sets the programme's company settings.
const STATUSES = ["Registered", "Approved", "Visited", "Booked", "Expired", "Rejected"];
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
const reasons = reactive({});
const settings = reactive({
	partner_lead_limit: "",
	partner_protection_days: "",
	consent_wording: "",
	partner_confirmation_wording: "",
});

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
	} catch (e) {
		error.value = serverMessage(e, "The settings could not be saved.");
	}
}

onMounted(load);
</script>
