<template>
	<div data-testid="sellos-partner-register-page">
		<PageHeader
			title="Register a buyer"
			text="Register a buyer you brought. If the company does not already have them, the lead is protected in your firm's name once the company approves it."
			icon="lucide-user-plus"
		/>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-partner-register-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<p
			v-if="error"
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

		<form
			class="ui-card mb-ui-md"
			data-testid="sellos-partner-register-form"
			@submit.prevent="register"
		>
			<h2 class="ui-card-heading mb-ui-md">Buyer</h2>
			<div class="grid grid-cols-1 gap-x-ui-md gap-y-ui-md md:grid-cols-2">
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
					data-testid="sellos-partner-register-note"
				/>
			</div>
			<div class="mt-ui-md rounded-input border border-line-soft p-ui-md">
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
					You can register the buyer without it. The company then sees that consent is
					unknown.
				</p>
			</div>
			<p class="mt-ui-sm text-sm text-ink-muted" data-testid="sellos-partner-register-left">
				You can register {{ remaining }} more buyers this hour.
			</p>
			<div class="mt-ui-md">
				<AppButton
					type="submit"
					variant="primary"
					data-testid="sellos-partner-register-submit"
				>
					Register buyer
				</AppButton>
			</div>
		</form>

		<ListCard title="Your registrations">
			<EmptyState
				v-if="loaded && !loadError && !rows.length"
				title="No registrations yet"
				text="Register your first buyer above."
				icon="lucide-user-plus"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-partner-register-list">
				<li
					v-for="r in rows"
					:key="r.name"
					data-testid="sellos-partner-register-row"
					:data-name="r.name"
					:data-status="r.status"
					class="rounded-input border border-line-soft p-ui-md"
				>
					<div class="flex flex-wrap items-center gap-3">
						<span class="font-medium text-ink">{{ r.buyer_name }}</span>
						<span class="text-sm text-ink-muted">{{ r.phone_masked }}</span>
						<StatusBadge
							:tone="STATUS_TONE[r.status] || 'neutral'"
							:label="r.status"
							data-testid="sellos-partner-register-status"
						/>
					</div>
					<p v-if="r.protected_until" class="text-sm text-ink-muted">
						Protected in your firm's name until {{ r.protected_until }}.
					</p>
					<p
						v-if="r.rejection_reason"
						class="text-sm text-ink-muted"
						data-testid="sellos-partner-register-reason"
					>
						Rejected: {{ r.rejection_reason }}
					</p>
				</li>
			</ul>
		</ListCard>
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
import StatusBadge from "../components/StatusBadge.vue";
import { partnerRegistrationsApi as api } from "../company/partnerRegistrationsApi";
import { serverMessage } from "../crm/crmApi";

// A partner registers a buyer (SOS-P7-02). The consent wording is the company's, shown as it will be kept.
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
const form = reactive({ ...BLANK });

async function load() {
	loadError.value = "";
	try {
		const [info, mine] = await Promise.all([api.form(), api.mine()]);
		wording.value = info.consent_wording;
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
