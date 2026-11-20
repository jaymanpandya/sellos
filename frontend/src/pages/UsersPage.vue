<template>
	<div data-testid="sellos-users-page">
		<PageHeader
			title="Users"
			text="Invite the people who work in your company, set the mobile number that click to call rings first, and deactivate users who leave. A deactivated user can not sign in, and their open leads and tasks are listed so they can be handed to someone else."
			icon="lucide-user-cog"
		/>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-users-error"
			class="mb-ui-md text-sm text-accent"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-users-notice"
			class="mb-ui-md text-sm text-ink"
		>
			{{ notice }}
		</p>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-users-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<div
			class="mb-ui-md grid grid-cols-2 gap-ui-md md:grid-cols-4"
			data-testid="sellos-users-stats"
		>
			<StatCard label="Users" :value="users.length" icon="lucide-users" />
			<StatCard
				label="Active"
				:value="countOf('Active')"
				icon="lucide-user-check"
				tone="success"
			/>
			<StatCard label="Invited" :value="countOf('Invited')" icon="lucide-mail" tone="info" />
			<StatCard
				label="Deactivated"
				:value="countOf('Deactivated')"
				icon="lucide-user-x"
				tone="warning"
			/>
		</div>

		<form
			class="ui-card mb-ui-md"
			data-testid="sellos-users-invite-form"
			@submit.prevent="invite"
		>
			<h2 class="ui-card-heading mb-ui-md">Invite a user</h2>
			<div class="grid grid-cols-1 gap-x-ui-md gap-y-ui-md md:grid-cols-2">
				<FormField
					v-model="form.email"
					type="email"
					label="Email"
					required
					data-testid="sellos-users-email"
				/>
				<FormField
					v-model="form.role"
					type="select"
					label="Role"
					:options="roleOptions"
					data-testid="sellos-users-role"
				/>
				<FormField
					v-model="form.first_name"
					label="First name"
					required
					data-testid="sellos-users-first-name"
				/>
				<FormField
					v-model="form.last_name"
					label="Last name"
					data-testid="sellos-users-last-name"
				/>
				<FormField
					v-model="form.mobile_no"
					type="tel"
					label="Mobile number"
					hint="+91 and ten digits."
					class="md:col-span-2"
					data-testid="sellos-users-mobile"
				/>
			</div>
			<div class="mt-ui-md">
				<AppButton type="submit" variant="primary" data-testid="sellos-users-invite">
					Send invitation
				</AppButton>
			</div>
		</form>

		<p
			v-if="!mailReady"
			data-testid="sellos-users-mail-note"
			class="mb-ui-md text-sm text-ink-muted"
		>
			This company can not send email yet, so an invitation is saved but not sent. Use Send
			invitation again once email is set up.
		</p>

		<ListCard title="People">
			<ul class="divide-y divide-line-soft" data-testid="sellos-users-list">
				<li
					v-for="u in users"
					:key="u.email"
					data-testid="sellos-users-row"
					:data-email="u.email"
					:data-status="u.status"
					class="space-y-ui-sm py-ui-md first:pt-0 last:pb-0"
				>
					<div class="flex flex-wrap items-center gap-3">
						<span class="font-medium text-ink" data-testid="sellos-users-name">
							{{ u.full_name || u.email }}
						</span>
						<span class="text-sm text-ink-muted">{{ u.email }}</span>
						<span class="text-sm text-ink-muted" data-testid="sellos-users-role-label">
							{{ roleLabel(u.role) }}
						</span>
						<StatusBadge
							:tone="STATUS_TONE[u.status] || 'neutral'"
							:label="u.status"
							data-testid="sellos-users-status"
						/>
					</div>
					<div class="flex flex-wrap items-end gap-ui-sm">
						<FormField
							v-model="mobiles[u.email]"
							type="tel"
							label="Mobile number"
							class="w-64"
							data-testid="sellos-users-row-mobile"
						/>
						<AppButton
							type="button"
							data-testid="sellos-users-save-mobile"
							@click="saveMobile(u)"
						>
							Save number
						</AppButton>
					</div>
					<p
						v-if="u.click_to_call_note"
						data-testid="sellos-users-no-click-to-call"
						class="text-sm text-accent"
					>
						{{ u.click_to_call_note }}
					</p>
					<p
						v-else
						class="text-sm text-ink-muted"
						data-testid="sellos-users-click-to-call"
					>
						Click to call rings this number first.
					</p>
					<div class="flex flex-wrap items-center gap-3 text-sm text-ink-muted">
						<span data-testid="sellos-users-open-leads"
							>{{ u.open_leads }} open leads</span
						>
						<span data-testid="sellos-users-open-tasks"
							>{{ u.open_tasks }} open tasks</span
						>
						<AppButton
							v-if="u.status === 'Invited'"
							type="button"
							data-testid="sellos-users-resend"
							@click="resend(u)"
						>
							Send invitation again
						</AppButton>
						<AppButton
							v-if="u.enabled && u.email !== session.user"
							type="button"
							data-testid="sellos-users-deactivate"
							@click="deactivate(u)"
						>
							Deactivate
						</AppButton>
						<AppButton
							v-if="!u.enabled"
							type="button"
							data-testid="sellos-users-reactivate"
							@click="reactivate(u)"
						>
							Turn back on
						</AppButton>
					</div>
					<div
						v-if="work && work.email === u.email"
						data-testid="sellos-users-work"
						class="rounded-input border border-line-soft p-ui-md text-sm"
					>
						<p v-if="work.needs_handover" class="font-medium text-ink">
							{{ u.full_name || u.email }} still has open work. Choose who takes it
							before you deactivate them:
						</p>
						<p v-else class="font-medium text-ink">
							{{ u.full_name || u.email }} can no longer sign in.
							<span v-if="handedOver" data-testid="sellos-users-handed-over">
								{{ handedOver }}
							</span>
						</p>
						<p
							v-if="!work.open_lead_count && !work.open_task_count"
							class="text-ink-muted"
						>
							No open leads or tasks.
						</p>
						<ul class="mt-1 list-disc pl-5">
							<li
								v-for="lead in work.open_leads"
								:key="lead.name"
								data-testid="sellos-users-work-lead"
							>
								Lead {{ lead.lead_title || lead.name }} ({{ lead.stage }})
							</li>
							<li
								v-for="t in work.open_tasks"
								:key="t.name"
								data-testid="sellos-users-work-task"
							>
								Task {{ t.title }}, due {{ t.due_date }}
							</li>
						</ul>
						<form
							v-if="work.needs_handover"
							class="mt-ui-sm flex flex-wrap items-end gap-ui-sm"
							data-testid="sellos-users-handover"
							@submit.prevent="handOver(u)"
						>
							<FormField
								v-model="handoverTo"
								type="select"
								label="Who takes the leads"
								required
								:options="handoverOptions(work.agents)"
								class="w-72"
								data-testid="sellos-users-handover-agent"
							/>
							<AppButton type="submit" data-testid="sellos-users-handover-confirm">
								Hand over and deactivate
							</AppButton>
							<AppButton
								type="button"
								data-testid="sellos-users-handover-cancel"
								@click="work = null"
							>
								Cancel
							</AppButton>
						</form>
					</div>
				</li>
			</ul>
		</ListCard>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import StatCard from "../components/StatCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { usersApi } from "../company/usersApi";
import { serverMessage } from "../crm/crmApi";
import { session } from "../session";

// Users, for the Company Admin (SOS-P1-17). Every change is saved at once and the list is read back.
const users = ref([]);
const roles = ref([]);
const mailReady = ref(true);
const error = ref("");
const loadError = ref("");
const notice = ref("");
const work = ref(null);
const mobiles = reactive({});
const form = reactive({
	email: "",
	first_name: "",
	last_name: "",
	role: "SellOS Agent",
	mobile_no: "",
});

const roleLabel = (role) => (role || "").replace(/^SellOS /, "");

function take(state) {
	users.value = state.users;
	roles.value = state.roles;
	mailReady.value = state.mail_ready;
	for (const u of state.users) mobiles[u.email] = u.mobile_no || "";
}

const roleOptions = computed(() => roles.value.map((r) => ({ label: roleLabel(r), value: r })));
const STATUS_TONE = { Active: "success", Invited: "info", Deactivated: "neutral" };
const countOf = (status) => users.value.filter((u) => u.status === status).length;
const handoverOptions = (agents) => [
	{ label: "Share among the team's active agents", value: "__team" },
	...(agents || []).map((a) => ({ label: a.full_name, value: a.name })),
];

async function load() {
	loadError.value = "";
	try {
		take(await usersApi.list());
	} catch (e) {
		loadError.value = serverMessage(e, "The users could not be loaded.");
	}
}

async function run(action, fallback) {
	error.value = "";
	notice.value = "";
	try {
		return await action();
	} catch (e) {
		error.value = serverMessage(e, fallback);
		return null;
	}
}

async function invite() {
	const result = await run(
		() => usersApi.invite({ ...form }),
		"The invitation could not be sent."
	);
	if (!result) return;
	take(result);
	notice.value = result.invited
		? `Invitation sent to ${result.email}.`
		: `${result.email} was added. The invitation was not sent because email is not set up yet.`;
	Object.assign(form, { email: "", first_name: "", last_name: "", mobile_no: "" });
}

async function resend(u) {
	const result = await run(() => usersApi.resend(u.email), "The invitation could not be sent.");
	if (!result) return;
	take(result);
	notice.value = result.invited
		? `Invitation sent again to ${u.email}.`
		: "The invitation was not sent because email is not set up yet.";
}

async function saveMobile(u) {
	const result = await run(
		() => usersApi.save(u.email, { mobile_no: mobiles[u.email] }),
		"The number could not be saved."
	);
	if (result) {
		take(result);
		notice.value = `Saved the number for ${u.full_name || u.email}.`;
	}
}

const handoverTo = ref("");
const handedOver = ref("");

async function deactivate(u, choice = {}) {
	handedOver.value = "";
	const result = await run(
		() => usersApi.deactivate(u.email, choice),
		"The user could not be deactivated."
	);
	if (!result) return;
	take(result);
	work.value = result;
	if (result.needs_handover) {
		handoverTo.value = "";
		notice.value = "";
		return;
	}
	const moved = result.handed_over || {};
	if (moved.leads || moved.tasks || moved.visits) {
		handedOver.value = `${moved.leads} leads, ${moved.tasks} tasks and ${moved.visits} site visits were handed over.`;
	}
	notice.value = `${u.full_name || u.email} is deactivated.`;
}

// The Company Admin has chosen an agent, or the team, to take the leaving agent's work (SOS-P1-19).
function handOver(u) {
	return deactivate(
		u,
		handoverTo.value === "__team" ? { distribute: 1 } : { reassignTo: handoverTo.value }
	);
}

async function reactivate(u) {
	const result = await run(
		() => usersApi.reactivate(u.email),
		"The user could not be turned on."
	);
	if (!result) return;
	take(result);
	if (work.value?.email === u.email) work.value = null;
	notice.value = `${u.full_name || u.email} can sign in again.`;
}

onMounted(load);
</script>
