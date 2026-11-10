<template>
	<div class="max-w-3xl" data-testid="sellos-support-page">
		<h1 class="text-2xl font-semibold text-ink">Support access</h1>
		<p class="mt-2 text-ink-muted">
			Let SellOS support read your company's records for a limited time. Support can look and
			change nothing. Access ends by itself, after 4 hours at most, and every action is
			logged below.
		</p>

		<form
			class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4"
			data-testid="sellos-support-form"
			@submit.prevent="grant"
		>
			<p
				v-if="!loading && !users.length"
				data-testid="sellos-support-no-users"
				class="text-ink-muted"
			>
				No support user is set up for this company yet.
			</p>
			<select
				v-model="form.user"
				required
				data-testid="sellos-support-user"
				class="field"
				aria-label="Support user"
			>
				<option v-for="u in users" :key="u.user" :value="u.user">
					{{ u.full_name || u.user }}
				</option>
			</select>
			<select
				v-model.number="form.minutes"
				data-testid="sellos-support-duration"
				class="field"
				aria-label="How long"
			>
				<option v-for="d in DURATIONS" :key="d.minutes" :value="d.minutes">
					{{ d.label }}
				</option>
			</select>
			<input
				v-model="form.reason"
				data-testid="sellos-support-reason"
				placeholder="What do you need help with? (optional)"
				class="field"
			/>
			<p
				v-if="error"
				data-testid="sellos-support-error"
				role="alert"
				class="text-sm text-accent"
			>
				{{ error }}
			</p>
			<button
				type="submit"
				class="btn"
				data-testid="sellos-support-grant"
				:disabled="!users.length"
			>
				Give access
			</button>
		</form>

		<p
			v-if="loadError"
			data-testid="sellos-support-load-error"
			role="alert"
			class="mt-4 text-accent"
		>
			{{ loadError }}
		</p>
		<p v-else-if="loading" class="mt-4 text-ink-muted">Loading.</p>
		<p
			v-else-if="!grants.length"
			data-testid="sellos-support-empty"
			class="mt-4 text-ink-muted"
		>
			Support has no access, and has never been given any.
		</p>
		<ul class="mt-4 divide-y divide-line rounded-input border border-line bg-surface">
			<li
				v-for="g in grants"
				:key="g.name"
				data-testid="sellos-support-grant-row"
				class="px-4 py-3"
			>
				<div class="flex items-center justify-between gap-3">
					<span>
						<span class="block font-medium text-ink">{{ g.support_user_name }}</span>
						<span class="block text-sm text-ink-muted">
							{{ g.starts_at.slice(0, 16) }} to {{ g.expires_at.slice(0, 16) }}
							<span v-if="g.reason"> · {{ g.reason }}</span>
						</span>
					</span>
					<span class="flex items-center gap-2">
						<span
							data-testid="sellos-support-status"
							class="rounded-input bg-brand-light px-2 py-1 text-xs text-ink"
						>
							{{ g.status }}
						</span>
						<button
							v-if="g.status === 'Active'"
							type="button"
							class="rounded-input px-3 py-1 text-sm text-ink-muted hover:bg-brand-light"
							data-testid="sellos-support-revoke"
							@click="revoke(g)"
						>
							End now
						</button>
						<button
							type="button"
							class="rounded-input px-3 py-1 text-sm text-ink-muted hover:bg-brand-light"
							data-testid="sellos-support-show-log"
							@click="toggleLog(g)"
						>
							{{ open === g.name ? "Hide log" : "Show log" }}
						</button>
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
						{{ line.timestamp.slice(0, 19) }} · {{ line.user }} · {{ line.action }}
						<span v-if="line.path"> · {{ line.http_method }} {{ line.path }}</span>
					</li>
				</ul>
			</li>
		</ul>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import { serverMessage } from "../crm/crmApi";
import { DURATIONS, supportApi } from "../support/supportApi";

const users = ref([]);
const grants = ref([]);
const log = ref([]);
const open = ref(null);
const loading = ref(true);
const loadError = ref("");
const error = ref("");
const form = reactive({ user: "", minutes: 60, reason: "" });

async function load() {
	loadError.value = "";
	try {
		[users.value, grants.value] = await Promise.all([supportApi.users(), supportApi.grants()]);
		if (!form.user && users.value.length) form.user = users.value[0].user;
	} catch (e) {
		loadError.value = serverMessage(e, "Support access could not be loaded.");
		console.error("support access failed", e);
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
