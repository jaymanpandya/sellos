<template>
	<div class="max-w-3xl" data-testid="sellos-support-page">
		<PageHeader
			title="Support access"
			text="Let SellOS support read your company's records for a limited time. Support can look and change nothing. Access ends by itself, after 4 hours at most, and every action is logged below."
			icon="lucide-life-buoy"
		/>

		<div class="mb-ui-md grid grid-cols-2 gap-ui-md" data-testid="sellos-support-stats">
			<StatCard
				label="Access now"
				:value="activeCount"
				icon="lucide-shield-check"
				:tone="activeCount ? 'warning' : 'success'"
			/>
			<StatCard label="Times given" :value="grants.length" icon="lucide-history" />
		</div>

		<form
			class="ui-card space-y-ui-md"
			data-testid="sellos-support-form"
			@submit.prevent="grant"
		>
			<h2 class="ui-card-heading">Give access</h2>
			<p
				v-if="!loading && !users.length"
				data-testid="sellos-support-no-users"
				class="text-ink-muted"
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
				data-testid="sellos-support-reason"
			/>
			<p
				v-if="error"
				data-testid="sellos-support-error"
				role="alert"
				class="text-sm text-accent"
			>
				{{ error }}
			</p>
			<AppButton
				type="submit"
				variant="primary"
				data-testid="sellos-support-grant"
				:disabled="!users.length"
			>
				Give access
			</AppButton>
		</form>

		<div class="mt-ui-md">
			<div v-if="loadError" data-testid="sellos-support-load-error">
				<LoadError :message="loadError" @retry="load" />
			</div>
			<LoadingSkeleton v-else-if="loading" />
			<div v-else-if="!grants.length" data-testid="sellos-support-empty">
				<EmptyState
					title="Support has no access"
					text="Support has no access, and has never been given any."
					icon="lucide-shield"
				/>
			</div>
			<ListCard v-else title="Access given">
				<ul class="divide-y divide-line-soft">
					<li
						v-for="g in grants"
						:key="g.name"
						data-testid="sellos-support-grant-row"
						class="py-ui-sm"
					>
						<div class="flex flex-wrap items-center justify-between gap-3">
							<span>
								<span class="block font-medium text-ink">{{
									g.support_user_name
								}}</span>
								<span class="block text-sm text-ink-muted">
									{{ g.starts_at.slice(0, 16) }} to
									{{ g.expires_at.slice(0, 16) }}
									<span v-if="g.reason"> · {{ g.reason }}</span>
								</span>
							</span>
							<span class="flex flex-wrap items-center gap-2">
								<StatusBadge
									:tone="STATUS_TONE[g.status] || 'neutral'"
									:label="g.status"
									data-testid="sellos-support-status"
								/>
								<AppButton
									v-if="g.status === 'Active'"
									type="button"
									data-testid="sellos-support-revoke"
									@click="revoke(g)"
								>
									End now
								</AppButton>
								<AppButton
									type="button"
									data-testid="sellos-support-show-log"
									@click="toggleLog(g)"
								>
									{{ open === g.name ? "Hide log" : "Show log" }}
								</AppButton>
							</span>
						</div>
						<ul
							v-if="open === g.name"
							class="mt-3 space-y-1 text-sm"
							data-testid="sellos-support-log"
						>
							<li
								v-for="(line, i) in log"
								:key="i"
								data-testid="sellos-support-log-row"
								class="text-ink-muted"
							>
								{{ line.timestamp.slice(0, 19) }} · {{ line.user }} ·
								{{ line.action }}
								<span v-if="line.path">
									· {{ line.http_method }} {{ line.path }}</span
								>
							</li>
						</ul>
					</li>
				</ul>
			</ListCard>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import StatCard from "../components/StatCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { logBackgroundError } from "../api";
import { DURATIONS, supportApi } from "../support/supportApi";

const users = ref([]);
const grants = ref([]);
const log = ref([]);
const open = ref(null);
const loading = ref(true);
const loadError = ref("");
const error = ref("");
const form = reactive({ user: "", minutes: 60, reason: "" });

const userOptions = computed(() =>
	users.value.map((u) => ({ label: u.full_name || u.user, value: u.user }))
);
const durationOptions = DURATIONS.map((d) => ({ label: d.label, value: d.minutes }));
const STATUS_TONE = { Active: "success", Expired: "neutral", Revoked: "danger" };
const activeCount = computed(() => grants.value.filter((g) => g.status === "Active").length);

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

async function grant() {
	error.value = "";
	try {
		await supportApi.grant(form.user, form.minutes, form.reason);
		form.reason = "";
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

onMounted(load);
</script>
