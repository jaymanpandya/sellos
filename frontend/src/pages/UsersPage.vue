<template>
	<div class="max-w-4xl" data-testid="sellos-users-page">
		<h1 class="text-2xl font-semibold text-ink">Users</h1>
		<p class="mt-2 text-ink-muted">
			Invite the people who work in your company, set the mobile number that click to call
			rings first, and deactivate users who leave. A deactivated user can not sign in, and
			their open leads and tasks are listed so they can be handed to someone else.
		</p>
		<p v-if="error" role="alert" data-testid="sellos-users-error" class="mt-3 text-accent">
			{{ error }}
		</p>
		<p v-if="notice" role="status" data-testid="sellos-users-notice" class="mt-3 text-ink">
			{{ notice }}
		</p>

		<form
			class="mt-4 grid gap-3 rounded-input border border-line bg-surface p-4 sm:grid-cols-2"
			data-testid="sellos-users-invite-form"
			@submit.prevent="invite"
		>
			<h2 class="font-medium text-ink sm:col-span-2">Invite a user</h2>
			<input
				v-model="form.email"
				type="email"
				required
				placeholder="Email"
				aria-label="Email"
				data-testid="sellos-users-email"
				class="field"
			/>
			<select
				v-model="form.role"
				aria-label="Role"
				data-testid="sellos-users-role"
				class="field"
			>
				<option v-for="r in roles" :key="r" :value="r">{{ roleLabel(r) }}</option>
			</select>
			<input
				v-model="form.first_name"
				required
				placeholder="First name"
				aria-label="First name"
				data-testid="sellos-users-first-name"
				class="field"
			/>
			<input
				v-model="form.last_name"
				placeholder="Last name"
				aria-label="Last name"
				data-testid="sellos-users-last-name"
				class="field"
			/>
			<input
				v-model="form.mobile_no"
				placeholder="Mobile number, +91 and ten digits"
				aria-label="Mobile number"
				data-testid="sellos-users-mobile"
				class="field sm:col-span-2"
			/>
			<div class="sm:col-span-2">
				<button type="submit" class="btn" data-testid="sellos-users-invite">
					Send invitation
				</button>
			</div>
		</form>

		<p
			v-if="!mailReady"
			data-testid="sellos-users-mail-note"
			class="mt-3 text-sm text-ink-muted"
		>
			This company can not send email yet, so an invitation is saved but not sent. Use Send
			invitation again once email is set up.
		</p>

		<ul class="mt-4 space-y-3" data-testid="sellos-users-list">
			<li
				v-for="u in users"
				:key="u.email"
				data-testid="sellos-users-row"
				:data-email="u.email"
				:data-status="u.status"
				class="space-y-2 rounded-input border border-line bg-surface p-4"
			>
				<div class="flex flex-wrap items-center gap-3">
					<span class="font-medium text-ink" data-testid="sellos-users-name">
						{{ u.full_name || u.email }}
					</span>
					<span class="text-sm text-ink-muted">{{ u.email }}</span>
					<span class="text-sm text-ink-muted" data-testid="sellos-users-role-label">
						{{ roleLabel(u.role) }}
					</span>
					<span class="text-sm text-ink" data-testid="sellos-users-status">
						{{ u.status }}
					</span>
				</div>
				<div class="flex flex-wrap items-center gap-2">
					<input
						v-model="mobiles[u.email]"
						placeholder="Mobile number"
						aria-label="Mobile number"
						data-testid="sellos-users-row-mobile"
						class="field w-56"
					/>
					<button
						type="button"
						class="btn"
						data-testid="sellos-users-save-mobile"
						@click="saveMobile(u)"
					>
						Save number
					</button>
					<span
						v-if="u.click_to_call_note"
						data-testid="sellos-users-no-click-to-call"
						class="text-sm text-accent"
					>
						{{ u.click_to_call_note }}
					</span>
					<span
						v-else
						class="text-sm text-ink-muted"
						data-testid="sellos-users-click-to-call"
					>
						Click to call rings this number first.
					</span>
				</div>
				<div class="flex flex-wrap items-center gap-3 text-sm text-ink-muted">
					<span data-testid="sellos-users-open-leads"
						>{{ u.open_leads }} open leads</span
					>
					<span data-testid="sellos-users-open-tasks"
						>{{ u.open_tasks }} open tasks</span
					>
					<button
						v-if="u.status === 'Invited'"
						type="button"
						class="btn"
						data-testid="sellos-users-resend"
						@click="resend(u)"
					>
						Send invitation again
					</button>
					<button
						v-if="u.enabled && u.email !== session.user"
						type="button"
						class="btn"
						data-testid="sellos-users-deactivate"
						@click="deactivate(u)"
					>
						Deactivate
					</button>
					<button
						v-if="!u.enabled"
						type="button"
						class="btn"
						data-testid="sellos-users-reactivate"
						@click="reactivate(u)"
					>
						Turn back on
					</button>
				</div>
				<div
					v-if="work && work.email === u.email"
					data-testid="sellos-users-work"
					class="rounded-input border border-line p-3 text-sm"
				>
					<p class="font-medium text-ink">
						{{ u.full_name || u.email }} can no longer sign in. These need a new owner:
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
				</div>
			</li>
		</ul>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import { usersApi } from "../company/usersApi";
import { serverMessage } from "../crm/crmApi";
import { session } from "../session";

// Users, for the Company Admin (SOS-P1-17). Every change is saved at once and the list is read back.
const users = ref([]);
const roles = ref([]);
const mailReady = ref(true);
const error = ref("");
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

async function load() {
	try {
		take(await usersApi.list());
	} catch (e) {
		error.value = serverMessage(e, "The users could not be loaded.");
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

async function deactivate(u) {
	const result = await run(
		() => usersApi.deactivate(u.email),
		"The user could not be deactivated."
	);
	if (!result) return;
	take(result);
	work.value = result;
	notice.value = `${u.full_name || u.email} is deactivated.`;
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
