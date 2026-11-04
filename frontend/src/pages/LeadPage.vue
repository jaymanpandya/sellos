<template>
	<div v-if="detail" class="max-w-3xl">
		<router-link :to="listPath" class="text-sm text-ink-muted">Back to leads</router-link>
		<div class="mt-2 flex items-start justify-between gap-3">
			<div>
				<h1 class="text-2xl font-semibold text-ink">{{ detail.client.client_name }}</h1>
				<p class="text-sm text-ink-muted">
					{{ detail.client.client_type }} · {{ detail.client.phone || "No phone" }}
					<span v-if="detail.client.overseas_phone">
						· {{ detail.client.overseas_phone }}</span
					>
				</p>
			</div>
			<button v-if="canLog" type="button" class="btn" @click="archive">Archive</button>
		</div>

		<section
			v-if="canLog"
			class="mt-6 space-y-3 rounded-input border border-line bg-surface p-4"
		>
			<h2 class="font-medium text-ink">Log something</h2>
			<form class="flex flex-wrap gap-2" @submit.prevent="logActivity">
				<select v-model="activity.type" class="field w-auto">
					<option v-for="t in ACTIVITY_TYPES" :key="t">{{ t }}</option>
				</select>
				<input v-model="activity.notes" placeholder="Notes" class="field flex-1" />
				<button type="submit" class="btn">Add activity</button>
			</form>
			<form class="flex flex-wrap gap-2" @submit.prevent="addTask">
				<input v-model="task.title" required placeholder="Task" class="field flex-1" />
				<input v-model="task.due_date" required type="date" class="field w-auto" />
				<button type="submit" class="btn">Add task</button>
			</form>
			<form class="flex flex-wrap gap-2" @submit.prevent="addVisit">
				<input
					v-model="visit.project_name"
					required
					placeholder="Site visit: project"
					class="field flex-1"
				/>
				<input
					v-model="visit.visit_datetime"
					required
					type="datetime-local"
					class="field w-auto"
				/>
				<button type="submit" class="btn">Add visit</button>
			</form>
		</section>

		<h2 class="mt-6 font-medium text-ink">Timeline</h2>
		<p v-if="!detail.timeline.length" class="mt-2 text-ink-muted">Nothing logged yet.</p>
		<ul class="mt-2 space-y-2">
			<li
				v-for="item in detail.timeline"
				:key="item.kind + item.name"
				class="rounded-input border border-line bg-surface p-3"
			>
				<div class="flex items-center justify-between gap-2">
					<span class="font-medium text-ink">
						<span class="mr-2 text-xs uppercase text-ink-muted">{{ item.kind }}</span
						>{{ item.title }}
					</span>
					<span
						v-if="item.overdue"
						class="rounded-input bg-accent px-2 py-1 text-xs text-white"
						>Overdue</span
					>
					<span v-else-if="item.status" class="text-xs text-ink-muted">{{
						item.status
					}}</span>
				</div>
				<p class="text-sm text-ink-muted">{{ String(item.when).slice(0, 16) }}</p>
				<p v-if="item.notes" class="mt-1 text-sm text-ink">{{ item.notes }}</p>
				<button
					v-if="canLog && item.kind === 'task' && item.status !== 'Done'"
					type="button"
					class="mt-2 text-sm text-ink-muted underline"
					@click="done(item)"
				>
					Mark done
				</button>
			</li>
		</ul>
	</div>
	<p v-else class="text-ink-muted">{{ error || "Loading" }}</p>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { ACTIVITY_TYPES, crmApi } from "../crm/crmApi";

const route = useRoute();
const router = useRouter();
const partner = computed(() => route.meta.area === "partner");
const canLog = computed(() => !partner.value); // a partner reads the timeline but does not log
const listPath = computed(() => (partner.value ? "/partner/leads" : "/crm/leads"));
const detail = ref(null);
const error = ref("");
const activity = reactive({ type: "Call", notes: "" });
const task = reactive({ title: "", due_date: "" });
const visit = reactive({ project_name: "", visit_datetime: "" });

async function load() {
	try {
		detail.value = (await crmApi.getLead(route.params.name)).message;
	} catch (e) {
		error.value = "This lead could not be opened.";
	}
}

async function logActivity() {
	await crmApi.addActivity(route.params.name, activity.type, activity.notes);
	activity.notes = "";
	await load();
}

async function addTask() {
	await crmApi.saveTask({ lead: route.params.name, ...task });
	task.title = "";
	task.due_date = "";
	await load();
}

async function addVisit() {
	await crmApi.saveSiteVisit({ lead: route.params.name, ...visit });
	visit.project_name = "";
	visit.visit_datetime = "";
	await load();
}

async function done(item) {
	await crmApi.saveTask({ status: "Done" }, item.name);
	await load();
}

async function archive() {
	await crmApi.setArchived("Lead", route.params.name);
	router.push(listPath.value);
}

onMounted(load);
</script>
