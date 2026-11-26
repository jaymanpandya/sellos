<template>
	<PageTemplate data-testid="sellos-support-page">
		<template #header>
			<PageHeader
				title="Support access"
				text="Let SellOS support read your company's records for a limited time. Access ends by itself, after 4 hours at most, and every action is logged."
				icon="lucide-life-buoy"
			>
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-support-add"
					@click="openGrant"
				>
					<template #prefix
						><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
					/></template>
					Give access
				</AppButton>
			</PageHeader>
		</template>

		<template #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-support-stats" />
		</template>

		<FormDrawer
			:open="granting"
			title="Give access"
			text="Support can look and change nothing. You can end it at any time."
			submit-label="Give access"
			:busy="!users.length"
			testid="sellos-support-form"
			submit-testid="sellos-support-grant"
			@close="granting = false"
			@submit="grant"
		>
			<FormSection title="Who and how long">
				<p
					v-if="!loading && !users.length"
					data-testid="sellos-support-no-users"
					class="md:col-span-2 ui-text-muted"
				>
					No support user is set up for this company yet.
				</p>
				<FormField
					v-model="form.user"
					type="select"
					label="Support user"
					required
					:options="userOptions"
					data-testid="sellos-support-user"
				/>
				<FormField
					v-model="form.minutes"
					type="select"
					label="How long"
					:options="durationOptions"
					data-testid="sellos-support-duration"
				/>
				<FormField
					v-model="form.reason"
					label="What do you need help with?"
					hint="Optional."
					class="md:col-span-2"
					data-testid="sellos-support-reason"
				/>
			</FormSection>
			<p v-if="error" data-testid="sellos-support-error" role="alert" class="ui-text-error">
				{{ error }}
			</p>
		</FormDrawer>

		<p
			v-if="error && !granting"
			data-testid="sellos-support-error"
			role="alert"
			class="mb-ui-md ui-text-error"
		>
			{{ error }}
		</p>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-support-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<DataTable
			v-else
			title="Access given"
			caption="Support access grants"
			:columns="columns"
			:rows="grants"
			:actions="rowActions"
			:loading="loading"
			loading-label="Loading support access."
			empty-title="Support has no access"
			empty-text="Support has no access, and has never been given any."
			empty-icon="lucide-shield"
			testid="sellos-support-list"
			row-testid="sellos-support-grant-row"
			empty-testid="sellos-support-empty"
		>
			<template #cell-support_user_name="{ row }">
				<NameCell :name="row.support_user_name" />
			</template>
			<template #cell-period="{ row }">
				<CellText :value="formatDateTime(row.starts_at)" />
				<CellText :value="`to ${formatDateTime(row.expires_at)}`" muted />
			</template>
			<template #cell-reason="{ row }">
				<CellText :value="row.reason" :lines="2" />
			</template>
			<template #cell-status="{ row }">
				<StatusBadge
					:tone="STATUS_TONE[row.status] || 'neutral'"
					:label="row.status"
					data-testid="sellos-support-status"
				/>
			</template>
		</DataTable>

		<!-- The log of the grant that was opened: who did what, and when. -->
		<ListCard v-if="open" title="Log" class="mt-ui-md">
			<ul class="space-y-1 ui-text-small" data-testid="sellos-support-log">
				<li
					v-for="(line, i) in log"
					:key="i"
					data-testid="sellos-support-log-row"
					class="ui-text-muted"
				>
					{{ line.timestamp.slice(0, 19) }} · {{ line.user }} · {{ line.action }}
					<span v-if="line.path"> · {{ line.http_method }} {{ line.path }}</span>
				</li>
			</ul>
		</ListCard>
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
import KpiStrip from "../components/KpiStrip.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { logBackgroundError } from "../api";
import { formatDateTime } from "../format";
import { DURATIONS, supportApi } from "../support/supportApi";

const users = ref([]);
const grants = ref([]);
const log = ref([]);
const open = ref(null);
const loading = ref(true);
const loadError = ref("");
const error = ref("");
const granting = ref(false);
const form = reactive({ user: "", minutes: 60, reason: "" });

const userOptions = computed(() =>
	users.value.map((u) => ({ label: u.full_name || u.user, value: u.user }))
);
const durationOptions = DURATIONS.map((d) => ({ label: d.label, value: d.minutes }));
const STATUS_TONE = { Active: "success", Expired: "neutral", Revoked: "danger" };
const activeCount = computed(() => grants.value.filter((g) => g.status === "Active").length);
const kpis = computed(() => [
	{
		label: "Access now",
		value: activeCount.value,
		caption: activeCount.value ? "support can read your records" : "support has no access",
		icon: "lucide-shield-check",
		tone: activeCount.value ? "warning" : "success",
	},
	{
		label: "Times given",
		value: grants.value.length,
		caption: "grants so far",
		icon: "lucide-history",
	},
]);
const columns = [
	{ key: "support_user_name", label: "Support user", primary: true },
	{ key: "period", label: "Period" },
	{ key: "reason", label: "Reason" },
	{ key: "status", label: "Status" },
];

async function load() {
	loadError.value = "";
	try {
		[users.value, grants.value] = await Promise.all([supportApi.users(), supportApi.grants()]);
		if (!form.user && users.value.length) form.user = users.value[0].user;
	} catch (e) {
		loadError.value = serverMessage(e, "Support access could not be loaded.");
		logBackgroundError("support access failed", e);
	} finally {
		loading.value = false;
	}
}

function openGrant() {
	error.value = "";
	granting.value = true;
}

async function grant() {
	error.value = "";
	try {
		await supportApi.grant(form.user, form.minutes, form.reason);
		form.reason = "";
		granting.value = false;
		await load();
	} catch (e) {
		error.value = serverMessage(e, "Access could not be given.");
	}
}

async function revoke(g) {
	error.value = "";
	try {
		await supportApi.revoke(g.name);
		await load();
		if (open.value === g.name) log.value = await supportApi.log(g.name);
	} catch (e) {
		error.value = serverMessage(e, "Access could not be ended.");
	}
}

async function toggleLog(g) {
	if (open.value === g.name) {
		open.value = null;
		return;
	}
	try {
		log.value = await supportApi.log(g.name);
		open.value = g.name;
	} catch (e) {
		error.value = serverMessage(e, "The log could not be loaded.");
	}
}

// Every row action is in the row menu (docs/DESIGN_SYSTEM.md, "Lists", rule c).
const rowActions = (g) => [
	...(g.status === "Active" ? [{ label: "End now", onClick: () => revoke(g) }] : []),
	{ label: open.value === g.name ? "Hide log" : "Show log", onClick: () => toggleLog(g) },
];

onMounted(load);
</script>
