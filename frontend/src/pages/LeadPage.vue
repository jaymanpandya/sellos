<template>
	<div v-if="detail" class="max-w-3xl" data-testid="sellos-lead-page">
		<router-link :to="listPath" data-testid="sellos-lead-back" class="text-sm text-ink-muted"
			>Back to leads</router-link
		>
		<div class="mt-2 flex items-start justify-between gap-3">
			<div>
				<h1 class="text-2xl font-semibold text-ink" data-testid="sellos-lead-name">
					{{ detail.client.client_name }}
				</h1>
				<p class="text-sm text-ink-muted">
					{{ detail.client.client_type }} ·
					<span data-testid="sellos-lead-phone">{{
						detail.client.phone || "No phone"
					}}</span>
					<span v-if="detail.client.overseas_phone">
						· {{ detail.client.overseas_phone }}</span
					>
				</p>
			</div>
			<button
				v-if="canLog"
				type="button"
				class="btn"
				data-testid="sellos-lead-archive"
				@click="archive"
			>
				Archive
			</button>
		</div>

		<section
			v-if="detail.consent"
			data-testid="sellos-lead-consent"
			:data-status="detail.consent.status"
			class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4"
		>
			<div class="flex flex-wrap items-center justify-between gap-2">
				<h2 class="font-medium text-ink">Consent</h2>
				<span data-testid="sellos-lead-consent-status" class="text-sm text-ink-muted">{{
					detail.consent.status
				}}</span>
			</div>
			<p
				v-if="detail.consent.warning"
				role="alert"
				data-testid="sellos-lead-consent-warning"
				:data-level="detail.consent.warning"
				class="rounded-input border px-3 py-2 text-sm"
				:class="
					detail.consent.warning === 'red'
						? 'border-[#c0392b] bg-[#fdecea] text-[#8e1f14]'
						: 'border-[#e8954a] bg-[#fdf1e3] text-[#7a4a10]'
				"
			>
				{{ detail.consent.message }} You can still call and message this lead.
			</p>
			<ul v-if="detail.consent.records.length" data-testid="sellos-lead-consent-records">
				<li
					v-for="record in detail.consent.records"
					:key="record.name"
					data-testid="sellos-lead-consent-record"
					class="text-sm text-ink-muted"
				>
					{{ record.basis }}, {{ String(record.recorded_on).slice(0, 16) }},
					{{
						record.expires_on
							? (record.live ? "expires " : "expired ") +
							  String(record.expires_on).slice(0, 16)
							: "no expiry"
					}}
					<span v-if="record.renewal_count">, renewal {{ record.renewal_count }}</span>
					<a
						:href="record.evidence_link"
						target="_blank"
						rel="noopener"
						class="ml-1 underline"
						>Evidence</a
					>
				</li>
			</ul>
			<template v-if="canLog">
				<form
					class="flex flex-wrap gap-2"
					data-testid="sellos-lead-consent-form"
					@submit.prevent="addConsent"
				>
					<select
						v-model="consentForm.basis"
						data-testid="sellos-lead-consent-basis"
						class="field w-auto"
					>
						<option v-for="b in CONSENT_BASES" :key="b">{{ b }}</option>
					</select>
					<input
						v-model="consentForm.evidence"
						data-testid="sellos-lead-consent-evidence"
						required
						placeholder="Evidence link"
						class="field flex-1"
					/>
					<button type="submit" class="btn" data-testid="sellos-lead-consent-save">
						Record basis
					</button>
				</form>
				<p
					v-if="consentError"
					data-testid="sellos-lead-consent-error"
					class="text-sm text-accent"
				>
					{{ consentError }}
				</p>
				<div class="flex flex-wrap gap-2">
					<select
						v-model="stopSource"
						data-testid="sellos-lead-optout-source"
						class="field w-auto"
					>
						<option v-for="s in STOP_SOURCES" :key="s">{{ s }}</option>
					</select>
					<button
						type="button"
						class="btn"
						data-testid="sellos-lead-optout"
						@click="optOut"
					>
						Record stop request
					</button>
					<button
						type="button"
						class="btn"
						data-testid="sellos-lead-dnd"
						@click="setDnd(1)"
					>
						Number is on the DND list
					</button>
					<button
						v-if="detail.consent.status === 'Registered DND'"
						type="button"
						class="btn"
						data-testid="sellos-lead-dnd-clear"
						@click="setDnd(0)"
					>
						Number is not on the DND list
					</button>
				</div>
			</template>
		</section>

		<section
			data-testid="sellos-lead-requirements"
			class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4"
		>
			<h2 class="font-medium text-ink">Requirements</h2>
			<form v-if="canLog" class="space-y-3" @submit.prevent="saveRequirements">
				<div class="flex flex-wrap gap-2">
					<input
						v-model.number="req.budget_from"
						data-testid="sellos-lead-req-budget-from"
						type="number"
						min="0"
						placeholder="Budget from (rupees)"
						class="field flex-1"
					/>
					<input
						v-model.number="req.budget_to"
						data-testid="sellos-lead-req-budget-to"
						type="number"
						min="0"
						placeholder="Budget to (rupees)"
						class="field flex-1"
					/>
				</div>
				<fieldset class="flex flex-wrap gap-3 text-sm text-ink">
					<legend class="text-ink-muted">Configuration</legend>
					<label v-for="c in CONFIGURATIONS" :key="c" class="flex items-center gap-1">
						<input
							v-model="req.configuration"
							type="checkbox"
							:value="c"
							data-testid="sellos-lead-req-configuration"
						/>
						{{ c }}
					</label>
				</fieldset>
				<div class="flex flex-wrap gap-2">
					<select
						v-model="req.property_type"
						data-testid="sellos-lead-req-property-type"
						class="field w-auto"
					>
						<option value="">Property type</option>
						<option v-for="o in PROPERTY_TYPES" :key="o">{{ o }}</option>
					</select>
					<select
						v-model="req.purpose"
						data-testid="sellos-lead-req-purpose"
						class="field w-auto"
					>
						<option value="">Purpose</option>
						<option v-for="o in PURPOSES" :key="o">{{ o }}</option>
					</select>
					<select
						v-model="req.timeline"
						data-testid="sellos-lead-req-timeline"
						class="field w-auto"
					>
						<option value="">Timeline</option>
						<option v-for="o in TIMELINES" :key="o">{{ o }}</option>
					</select>
					<select
						v-model="req.possession"
						data-testid="sellos-lead-req-possession"
						class="field w-auto"
					>
						<option value="">Possession</option>
						<option v-for="o in POSSESSIONS" :key="o">{{ o }}</option>
					</select>
				</div>
				<input
					v-model="req.localities"
					data-testid="sellos-lead-req-localities"
					placeholder="Preferred localities, separated by commas"
					class="field"
				/>
				<p
					v-if="requirementsError"
					role="alert"
					data-testid="sellos-lead-req-error"
					class="text-sm text-accent"
				>
					{{ requirementsError }}
				</p>
				<button type="submit" class="btn" data-testid="sellos-lead-req-save">
					Save requirements
				</button>
			</form>
			<p data-testid="sellos-lead-req-summary" class="text-sm text-ink-muted">
				{{ summary }}
			</p>
		</section>

		<section
			v-if="canLog"
			data-testid="sellos-lead-log"
			class="mt-6 space-y-3 rounded-input border border-line bg-surface p-4"
		>
			<h2 class="font-medium text-ink">Log something</h2>
			<form
				class="flex flex-wrap gap-2"
				data-testid="sellos-lead-activity-form"
				@submit.prevent="logActivity"
			>
				<select
					v-model="activity.type"
					data-testid="sellos-lead-activity-type"
					class="field w-auto"
				>
					<option v-for="t in ACTIVITY_TYPES" :key="t">{{ t }}</option>
				</select>
				<input
					v-model="activity.notes"
					data-testid="sellos-lead-activity-notes"
					placeholder="Notes"
					class="field flex-1"
				/>
				<button type="submit" class="btn" data-testid="sellos-lead-activity-save">
					Add activity
				</button>
			</form>
			<form
				class="flex flex-wrap gap-2"
				data-testid="sellos-lead-task-form"
				@submit.prevent="addTask"
			>
				<input
					v-model="task.title"
					data-testid="sellos-lead-task-title"
					required
					placeholder="Task"
					class="field flex-1"
				/>
				<input
					v-model="task.due_date"
					data-testid="sellos-lead-task-due"
					required
					type="date"
					class="field w-auto"
				/>
				<button type="submit" class="btn" data-testid="sellos-lead-task-save">
					Add task
				</button>
			</form>
			<form
				class="flex flex-wrap gap-2"
				data-testid="sellos-lead-visit-form"
				@submit.prevent="addVisit"
			>
				<input
					v-model="visit.project_name"
					data-testid="sellos-lead-visit-project"
					required
					placeholder="Site visit: project"
					class="field flex-1"
				/>
				<input
					v-model="visit.visit_datetime"
					data-testid="sellos-lead-visit-when"
					required
					type="datetime-local"
					class="field w-auto"
				/>
				<button type="submit" class="btn" data-testid="sellos-lead-visit-save">
					Add visit
				</button>
			</form>
		</section>

		<h2 class="mt-6 font-medium text-ink">Timeline</h2>
		<p
			v-if="!detail.timeline.length"
			data-testid="sellos-lead-timeline-empty"
			class="mt-2 text-ink-muted"
		>
			Nothing logged yet.
		</p>
		<ul class="mt-2 space-y-2" data-testid="sellos-lead-timeline">
			<li
				v-for="item in detail.timeline"
				data-testid="sellos-lead-timeline-item"
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
						data-testid="sellos-lead-timeline-overdue"
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
	<p v-else data-testid="sellos-lead-loading" class="text-ink-muted">{{ error || "Loading" }}</p>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import {
	ACTIVITY_TYPES,
	CONFIGURATIONS,
	CONSENT_BASES,
	POSSESSIONS,
	PROPERTY_TYPES,
	PURPOSES,
	STOP_SOURCES,
	TIMELINES,
	crmApi,
	serverMessage,
} from "../crm/crmApi";

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

const req = reactive({
	budget_from: "",
	budget_to: "",
	configuration: [],
	property_type: "",
	localities: "",
	purpose: "",
	timeline: "",
	possession: "",
});
const requirementsError = ref("");
const rupees = (n) => (n ? "₹" + Number(n).toLocaleString("en-IN") : "");
const requirementRows = computed(() => {
	const r = detail.value?.requirements || {};
	return [
		[
			"Budget",
			[rupees(r.budget_from), rupees(r.budget_to)].filter(Boolean).join(" to ") || "Not set",
		],
		["Configuration", (r.configuration || []).join(", ") || "Not set"],
		["Property type", r.property_type || "Not set"],
		["Preferred localities", (r.preferred_localities || []).join(", ") || "Not set"],
		["Purpose", r.purpose || "Not set"],
		["Timeline", r.timeline || "Not set"],
		["Possession", r.possession || "Not set"],
	];
});
const summary = computed(() => requirementRows.value.map((r) => `${r[0]} ${r[1]}`).join(". "));

function fillRequirements() {
	const r = detail.value.requirements || {};
	Object.assign(req, {
		budget_from: r.budget_from ?? "",
		budget_to: r.budget_to ?? "",
		configuration: [...(r.configuration || [])],
		property_type: r.property_type || "",
		localities: (r.preferred_localities || []).join(", "),
		purpose: r.purpose || "",
		timeline: r.timeline || "",
		possession: r.possession || "",
	});
}

async function saveRequirements() {
	requirementsError.value = "";
	try {
		const { localities, ...rest } = req;
		const saved = await crmApi.saveLead(
			{
				...rest,
				budget_from: req.budget_from || 0,
				budget_to: req.budget_to || 0,
				preferred_localities: localities
					.split(",")
					.map((l) => l.trim())
					.filter(Boolean),
			},
			route.params.name
		);
		detail.value = { ...detail.value, ...saved };
		fillRequirements();
	} catch (e) {
		requirementsError.value = serverMessage(e, "The requirements could not be saved.");
	}
}

async function load() {
	try {
		detail.value = await crmApi.getLead(route.params.name);
		fillRequirements();
	} catch (e) {
		error.value = "This lead could not be opened.";
	}
}

const consentForm = reactive({ basis: "Inquiry", evidence: "" });
const consentError = ref("");
const stopSource = ref("Phone call");

async function addConsent() {
	consentError.value = "";
	try {
		await crmApi.recordConsent(route.params.name, consentForm.basis, consentForm.evidence);
		consentForm.evidence = "";
		await load();
	} catch (e) {
		consentError.value = serverMessage(e, "The consent record could not be saved.");
	}
}

async function optOut() {
	await crmApi.recordOptOut(route.params.name, stopSource.value);
	await load();
}

async function setDnd(registered) {
	await crmApi.recordDndResult(route.params.name, registered);
	await load();
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
