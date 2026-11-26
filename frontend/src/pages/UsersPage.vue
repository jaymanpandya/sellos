<template>
	<PageTemplate data-testid="sellos-users-page">
		<template #header>
			<PageHeader
				title="Users"
				text="Invite the people who work in your company, set the mobile number that click to call rings first, and deactivate users who leave."
				icon="lucide-user-cog"
			>
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-users-add"
					@click="openInvite"
				>
					<template #prefix
						><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
					/></template>
					Add user
				</AppButton>
			</PageHeader>
		</template>

		<template #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-users-stats" />
		</template>

		<template #filters>
			<FilterBar
				v-model:search="search"
				search-label="Search users"
				search-placeholder="Search by name or email"
				search-testid="sellos-users-search"
				clear-testid="sellos-users-filter-clear"
				:active="Boolean(search || statusFilter || roleFilter)"
				:chips="chips"
				data-testid="sellos-users-filters"
				@clear="clearFilters"
				@remove-chip="removeChip"
			>
				<FormField
					v-model="roleFilter"
					compact
					type="select"
					label="Role"
					:options="roleFilterOptions"
					data-testid="sellos-users-filter-role"
				/>
				<FormField
					v-model="statusFilter"
					compact
					type="select"
					label="Status"
					:options="statusOptions"
					data-testid="sellos-users-filter-status"
				/>
			</FilterBar>
		</template>

		<FormDrawer
			:open="inviting"
			title="Add user"
			text="They get an email to set a password when your company can send email."
			submit-label="Send invitation"
			testid="sellos-users-invite-form"
			submit-testid="sellos-users-invite"
			@close="inviting = false"
			@submit="invite"
		>
			<FormSection title="Person">
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
			</FormSection>
			<p v-if="error" role="alert" data-testid="sellos-users-error" class="ui-text-error">
				{{ error }}
			</p>
		</FormDrawer>

		<p
			v-if="error && !inviting"
			role="alert"
			data-testid="sellos-users-error"
			class="mb-ui-md ui-text-error"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-users-notice"
			class="mb-ui-md ui-text-small"
		>
			{{ notice }}
		</p>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-users-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<p v-if="!mailReady" data-testid="sellos-users-mail-note" class="mb-ui-md ui-text-muted">
			This company can not send email yet, so an invitation is saved but not sent. Use Send
			invitation again once email is set up.
		</p>

		<!-- Deactivating a user: who takes their open work. A deactivated user can not sign in. -->
		<SectionCard
			v-if="work && workUser"
			title="Open work"
			data-testid="sellos-users-work"
			class="mb-ui-md space-y-ui-sm ui-text-small"
		>
			<p v-if="work.needs_handover" class="ui-text-strong">
				{{ leaving }} still has open work. Choose who takes it before you deactivate them:
			</p>
			<p v-else class="ui-text-strong">
				{{ leaving }} can no longer sign in.
				<span v-if="handedOver" data-testid="sellos-users-handed-over">
					{{ handedOver }}
				</span>
			</p>
			<p v-if="!work.open_lead_count && !work.open_task_count" class="ui-text-muted">
				No open leads or tasks.
			</p>
			<ul class="list-disc ml-5">
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
					Task {{ t.title }}, due {{ formatDate(t.due_date) }}
				</li>
			</ul>
			<form
				v-if="work.needs_handover"
				class="flex flex-wrap items-end gap-ui-sm"
				data-testid="sellos-users-handover"
				@submit.prevent="handOver(workUser)"
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
				<AppButton
					type="submit"
					variant="primary"
					data-testid="sellos-users-handover-confirm"
				>
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
			<AppButton
				v-else
				type="button"
				data-testid="sellos-users-work-close"
				@click="work = null"
			>
				Close
			</AppButton>
		</SectionCard>

		<DataTable
			title="People"
			caption="Users"
			:columns="columns"
			:rows="shown"
			row-key="email"
			:row-attrs="rowAttrs"
			:row-name="(u) => u.full_name || u.email"
			:loading="loading"
			loading-label="Loading users."
			empty-title="No users yet"
			empty-text="Add the first person with Add user."
			empty-icon="lucide-users"
			testid="sellos-users-list"
			row-testid="sellos-users-row"
		>
			<template #cell-full_name="{ row }">
				<span class="block ui-text-strong" data-testid="sellos-users-name">{{
					row.full_name || row.email
				}}</span>
				<span class="block ui-text-muted">{{ row.email }}</span>
			</template>
			<template #cell-role="{ row }">
				<span class="ui-text-secondary" data-testid="sellos-users-role-label">{{
					roleLabel(row.role)
				}}</span>
			</template>
			<template #cell-status="{ row }">
				<StatusBadge
					:tone="STATUS_TONE[row.status] || 'neutral'"
					:label="row.status"
					data-testid="sellos-users-status"
				/>
			</template>
			<template #cell-mobile_no="{ row }">
				<div class="flex flex-wrap items-end gap-ui-sm">
					<FormField
						v-model="mobiles[row.email]"
						type="tel"
						label="Mobile number"
						class="w-52"
						data-testid="sellos-users-row-mobile"
					/>
					<AppButton
						type="button"
						data-testid="sellos-users-save-mobile"
						@click="saveMobile(row)"
					>
						Save number
					</AppButton>
				</div>
				<p
					v-if="row.click_to_call_note"
					data-testid="sellos-users-no-click-to-call"
					class="mt-1 ui-text-error"
				>
					{{ row.click_to_call_note }}
				</p>
				<p v-else class="mt-1 ui-text-muted" data-testid="sellos-users-click-to-call">
					Click to call rings this number first.
				</p>
			</template>
			<template #cell-work="{ row }">
				<span class="block ui-text-muted" data-testid="sellos-users-open-leads"
					>{{ row.open_leads }} open leads</span
				>
				<span class="block ui-text-muted" data-testid="sellos-users-open-tasks"
					>{{ row.open_tasks }} open tasks</span
				>
			</template>
			<template #cell-actions="{ row }">
				<div class="flex flex-wrap items-center gap-ui-sm">
					<AppButton
						v-if="row.status === 'Invited'"
						type="button"
						data-testid="sellos-users-resend"
						@click="resend(row)"
					>
						Send invitation again
					</AppButton>
					<AppButton
						v-if="row.enabled && row.email !== session.user"
						type="button"
						data-testid="sellos-users-deactivate"
						@click="deactivate(row)"
					>
						Deactivate
					</AppButton>
					<AppButton
						v-if="!row.enabled"
						type="button"
						data-testid="sellos-users-reactivate"
						@click="reactivate(row)"
					>
						Turn back on
					</AppButton>
				</div>
			</template>
		</DataTable>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import FilterBar from "../components/FilterBar.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import SectionCard from "../components/SectionCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { usersApi } from "../company/usersApi";
import { serverMessage } from "../crm/crmApi";
import { formatDate } from "../format";
import { session } from "../session";

// Users, for the Company Admin (SOS-P1-17). Every change is saved at once and the list is read back.
const users = ref([]);
const roles = ref([]);
const mailReady = ref(true);
const error = ref("");
const loadError = ref("");
const loading = ref(true);
const notice = ref("");
const work = ref(null);
const inviting = ref(false);
const search = ref("");
const statusFilter = ref("");
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
const kpis = computed(() => [
	{
		label: "Users",
		value: users.value.length,
		caption: "in your company",
		icon: "lucide-users",
	},
	{
		label: "Active",
		value: countOf("Active"),
		caption: "can sign in",
		icon: "lucide-user-check",
		tone: "success",
	},
	{
		label: "Invited",
		value: countOf("Invited"),
		caption: "have not signed in yet",
		icon: "lucide-mail",
		tone: "info",
	},
	{
		label: "Deactivated",
		value: countOf("Deactivated"),
		caption: "can not sign in",
		icon: "lucide-user-x",
		tone: "warning",
	},
]);

// The search and the status filter work on the users already loaded.
const statusOptions = [
	{ label: "Any status", value: "" },
	{ label: "Active", value: "Active" },
	{ label: "Invited", value: "Invited" },
	{ label: "Deactivated", value: "Deactivated" },
];
const roleFilter = ref("");
const roleFilterOptions = computed(() => [
	{ label: "Any role", value: "" },
	...[...new Set(users.value.map((u) => u.role).filter(Boolean))]
		.sort()
		.map((r) => ({ label: roleLabel(r), value: r })),
]);
const chips = computed(() => [
	...(search.value ? [{ key: "search", label: `Search: ${search.value}` }] : []),
	...(statusFilter.value ? [{ key: "status", label: `Status: ${statusFilter.value}` }] : []),
	...(roleFilter.value ? [{ key: "role", label: `Role: ${roleLabel(roleFilter.value)}` }] : []),
]);
function removeChip(key) {
	if (key === "search") search.value = "";
	else if (key === "role") roleFilter.value = "";
	else statusFilter.value = "";
}
const shown = computed(() => {
	const q = search.value.trim().toLowerCase();
	return users.value.filter(
		(u) =>
			(!statusFilter.value || u.status === statusFilter.value) &&
			(!roleFilter.value || u.role === roleFilter.value) &&
			(!q || `${u.full_name || ""} ${u.email}`.toLowerCase().includes(q))
	);
});
function clearFilters() {
	search.value = "";
	statusFilter.value = "";
	roleFilter.value = "";
}

const columns = [
	{
		key: "full_name",
		label: "Name",
		primary: true,
		sortable: true,
		sortValue: (u) => u.full_name || u.email,
	},
	{ key: "role", label: "Role", sortable: true, sortValue: (u) => roleLabel(u.role) },
	{ key: "status", label: "Status", sortable: true },
	{ key: "mobile_no", label: "Mobile number", wrap: true, class: "min-w-[16rem]" },
	{ key: "work", label: "Open work" },
	{ key: "actions", label: "Actions" },
];
const rowAttrs = (u) => ({ "data-email": u.email, "data-status": u.status });
const workUser = computed(() => users.value.find((u) => u.email === work.value?.email) || null);
const leaving = computed(() => workUser.value?.full_name || work.value?.email || "");

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
	} finally {
		loading.value = false;
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

function openInvite() {
	error.value = "";
	inviting.value = true;
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
	inviting.value = false;
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
