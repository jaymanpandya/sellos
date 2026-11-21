<template>
	<div data-testid="sellos-partners-page">
		<PageHeader
			title="Channel partners"
			text="Invite a partner firm by email. Its contact person signs in, completes the firm's details, and the firm waits here for your approval. Only an approved firm may register leads."
			icon="lucide-handshake"
		/>
		<p
			v-if="error"
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

		<div
			class="mb-ui-md grid grid-cols-2 gap-ui-md md:grid-cols-4"
			data-testid="sellos-partners-stats"
		>
			<StatCard label="Invited" :value="counts['Invited'] || 0" icon="lucide-mail" />
			<StatCard
				label="Pending approval"
				:value="counts['Pending approval'] || 0"
				icon="lucide-clock"
				tone="warning"
			/>
			<StatCard
				label="Approved"
				:value="counts['Approved'] || 0"
				icon="lucide-badge-check"
				tone="success"
			/>
			<StatCard
				label="Suspended"
				:value="counts['Suspended'] || 0"
				icon="lucide-ban"
				tone="danger"
			/>
		</div>

		<ListCard title="Partner firms">
			<EmptyState
				v-if="loaded && !loadError && !firms.length"
				title="No partner firms yet"
				text="Invite the first firm below."
				icon="lucide-handshake"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-partners-list">
				<li
					v-for="f in firms"
					:key="f.name"
					data-testid="sellos-partners-row"
					:data-name="f.name"
					:data-status="f.status"
					class="rounded-input border border-line-soft p-ui-md"
				>
					<div class="flex flex-wrap items-center gap-3">
						<span class="font-medium text-ink" data-testid="sellos-partners-firm-name">
							{{ f.firm_name }}
						</span>
						<span class="text-sm text-ink-muted" data-testid="sellos-partners-code">
							{{ f.partner_code }}
						</span>
						<StatusBadge
							:tone="STATUS_TONE[f.status] || 'neutral'"
							:label="f.status"
							data-testid="sellos-partners-status"
						/>
					</div>
					<p class="mt-1 text-sm text-ink-muted">
						{{ f.contact_person }}, {{ f.email }}
						<span v-if="f.phone" data-testid="sellos-partners-phone"
							>, {{ f.phone }}</span
						>
					</p>
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

					<div class="mt-ui-sm flex flex-wrap items-end gap-ui-sm">
						<AppButton
							v-if="f.status === 'Pending approval'"
							type="button"
							variant="primary"
							data-testid="sellos-partners-approve"
							@click="
								act(() => partnersApi.approve(f.name), 'The firm was approved.')
							"
						>
							Approve
						</AppButton>
						<AppButton
							v-if="f.status === 'Suspended'"
							type="button"
							data-testid="sellos-partners-reinstate"
							@click="
								act(
									() => partnersApi.reinstate(f.name),
									'The firm was reinstated.'
								)
							"
						>
							Reinstate
						</AppButton>
						<template v-if="f.status !== 'Suspended'">
							<FormField
								v-model="reasons[f.name]"
								label="Reason for a suspension"
								class="w-72"
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

					<details class="mt-ui-sm" data-testid="sellos-partners-log">
						<summary class="cursor-pointer text-sm text-ink-muted">Status log</summary>
						<ul class="mt-1 space-y-1 text-sm text-ink-muted">
							<li
								v-for="(l, i) in f.log"
								:key="i"
								data-testid="sellos-partners-log-row"
							>
								{{ l.changed_on }}: {{ l.changed_by_name }} moved it
								<span v-if="l.from_status">from {{ l.from_status }}</span>
								to {{ l.to_status }}<span v-if="l.reason"> ({{ l.reason }})</span>
							</li>
						</ul>
					</details>
				</li>
			</ul>
		</ListCard>

		<form class="ui-card mt-ui-md" data-testid="sellos-partners-form" @submit.prevent="invite">
			<h2 class="ui-card-heading mb-ui-md">Invite a partner firm</h2>
			<div class="grid grid-cols-1 gap-x-ui-md gap-y-ui-md md:grid-cols-2">
				<FormField
					v-model="form.firm_name"
					label="Firm name"
					required
					data-testid="sellos-partners-firm"
				/>
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
			</div>
			<div class="mt-ui-md">
				<AppButton type="submit" variant="primary" data-testid="sellos-partners-invite">
					Invite firm
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
import { partnersApi } from "../company/partnersApi";
import { serverMessage } from "../crm/crmApi";

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
const reasons = reactive({});
const form = reactive({ firm_name: "", contact_person: "", email: "", phone: "" });

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
	if (done) Object.assign(form, { firm_name: "", contact_person: "", email: "", phone: "" });
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
