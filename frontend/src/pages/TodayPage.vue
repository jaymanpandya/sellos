<template>
	<div data-testid="sellos-today">
		<p class="mb-ui-md ui-text-muted" data-testid="sellos-today-scope">
			{{ scopeNote }}
		</p>
		<LoadError
			v-if="error"
			class="mb-ui-md"
			data-testid="sellos-today-error"
			:message="error"
			@retry="onRetry"
		/>
		<LoadingSkeleton v-else-if="!view" />

		<template v-if="view">
			<!-- The four counts as a row of chips: the dashboard above owns the page's one KPI strip. -->
			<ul class="mb-ui-md flex flex-wrap gap-ui-sm" data-testid="sellos-today-counts">
				<li v-for="s in SECTIONS" :key="s.key">
					<StatusBadge :tone="s.tone">
						{{ s.label }}
						<b
							class="ml-1 tabular-nums"
							:data-testid="`sellos-today-count-${s.key}`"
							>{{ view.counts[s.key] }}</b
						>
					</StatusBadge>
				</li>
			</ul>

			<SectionCard
				v-for="s in SECTIONS"
				:id="`today-${s.key}`"
				:key="s.key"
				:title="s.label"
				class="mb-ui-md"
				:data-testid="`sellos-today-section-${s.key}`"
			>
				<EmptyState
					v-if="!view[s.key].length"
					:data-testid="`sellos-today-empty-${s.key}`"
					:title="s.empty"
					:icon="s.icon"
				/>
				<template v-else-if="team">
					<div
						v-for="group in groups(s.key)"
						:key="group.agent"
						class="mb-ui-md"
						data-testid="sellos-today-agent"
						:data-agent="group.agent"
					>
						<p class="mb-1 ui-text-strong">
							{{ group.agent_name }} ({{ group.rows.length }})
						</p>
						<DataTable
							:caption="`${s.label}, ${group.agent_name}`"
							:columns="columnsFor(s.key)"
							:rows="group.rows"
							row-key="_key"
							v-bind="tableProps(s.key)"
						>
							<template #cell-lead_title="{ row }">
								<NameCell
									:name="row.lead_name || row.lead_title"
									:identifier="row.phone"
									:detail="row.lead_source"
									data-testid="sellos-today-lead"
								/>
							</template>
							<template #cell-detail="{ row }">
								<CellText :value="row.title || row.project_name" :lines="2" />
							</template>
							<template #cell-when="{ row }"
								><CellText :value="whenOf(row)"
							/></template>
							<template #cell-agent_name="{ row }"
								><CellText :value="row.agent_name"
							/></template>
							<template #cell-status="{ row }"><TodayBadges :row="row" /></template>
						</DataTable>
					</div>
				</template>
				<DataTable
					v-else
					:caption="s.label"
					:columns="columnsFor(s.key)"
					:rows="rowsOf(s.key)"
					row-key="_key"
					v-bind="tableProps(s.key)"
				>
					<template #cell-lead_title="{ row }">
						<NameCell
							:name="row.lead_name || row.lead_title"
							:identifier="row.phone"
							:detail="row.lead_source"
							data-testid="sellos-today-lead"
						/>
					</template>
					<template #cell-detail="{ row }">
						<CellText :value="row.title || row.project_name" :lines="2" />
					</template>
					<template #cell-when="{ row }"><CellText :value="whenOf(row)" /></template>
					<template #cell-agent_name="{ row }"
						><CellText :value="row.agent_name"
					/></template>
					<template #cell-status="{ row }"><TodayBadges :row="row" /></template>
				</DataTable>
			</SectionCard>
		</template>

		<!-- Calling a lead: the number the person's role may see, from the row menu. Consent never stops a call. -->
		<FormDrawer
			:open="Boolean(calling)"
			:title="calling ? `Call ${calling.lead_name || calling.lead_title}` : 'Call'"
			text="The number to dial. A consent warning never stops a call."
			submit-label="Done"
			testid="sellos-today-call-drawer"
			submit-testid="sellos-today-call-done"
			@close="calling = null"
			@submit="calling = null"
		>
			<p v-if="calling" class="ui-text-body" data-testid="sellos-today-number">
				<template v-if="calling.phone">
					<a v-if="view.full_numbers" :href="`tel:${calling.phone}`" class="ui-link">{{
						calling.phone
					}}</a>
					<span v-else>{{ calling.phone }}</span>
					<span v-if="calling.overseas_phone"> · {{ calling.overseas_phone }}</span>
				</template>
				<template v-else>No phone</template>
			</p>
		</FormDrawer>

		<!-- Rescheduling a visit asks for the new date and time. -->
		<FormDrawer
			:open="Boolean(rescheduling)"
			:title="
				rescheduling
					? `Reschedule ${rescheduling.lead_name || rescheduling.lead_title}`
					: 'Reschedule'
			"
			text="Choose the new date and time of the visit."
			submit-label="Reschedule"
			testid="sellos-visit-reschedule-form"
			submit-testid="sellos-visit-reschedule-save"
			cancel-testid="sellos-visit-reschedule-cancel"
			@close="closeReschedule"
			@submit="reschedule"
		>
			<FormField
				v-model="rescheduleWhen"
				required
				type="datetime-local"
				label="New date and time"
				data-testid="sellos-visit-reschedule-when"
			/>
			<p
				v-if="visitError"
				role="alert"
				class="ui-text-error"
				data-testid="sellos-visit-confirm-error"
			>
				{{ visitError }}
			</p>
		</FormDrawer>

		<!-- Log a call: a drawer, so no form sits open under a list. -->
		<FormDrawer
			:open="Boolean(logging)"
			title="Log a call"
			:text="logging ? logging.row.lead_title : ''"
			submit-label="Save"
			testid="sellos-today-log-form"
			submit-testid="sellos-today-log-save"
			@close="logging = null"
			@submit="saveLog"
		>
			<FormSection title="The call">
				<FormField
					v-model="form.outcome"
					type="select"
					label="Outcome"
					required
					:options="outcomeOptions"
					data-testid="sellos-today-log-outcome"
				/>
				<FormField
					v-model="form.notes"
					label="Notes"
					data-testid="sellos-today-log-notes"
				/>
				<FormField
					v-if="chosen?.needs_follow_up"
					v-model="form.followUp"
					required
					type="datetime-local"
					label="Follow up on"
					class="md:col-span-2"
					data-testid="sellos-today-log-follow-up"
				/>
			</FormSection>
			<p
				v-if="logError"
				role="alert"
				data-testid="sellos-today-log-error"
				class="ui-text-error"
			>
				{{ logError }}
			</p>
		</FormDrawer>
	</div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import CellText from "../components/CellText.vue";
import DataTable from "../components/DataTable.vue";
import EmptyState from "../components/EmptyState.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import NameCell from "../components/NameCell.vue";
import SectionCard from "../components/SectionCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { crmApi, serverMessage } from "../crm/crmApi";
import { formatWhen } from "../format";

// The Today screen (SOS-P1-26): what to do now, in four lists. A Sales Manager sees the same lists for
// the team, each grouped by agent. The counts come from the same answer as the lists.
const SECTIONS = [
	{
		key: "follow_ups",
		label: "Follow ups due and overdue",
		empty: "No follow ups due today.",
		icon: "lucide-clock-alert",
		tone: "danger",
	},
	{
		key: "new_leads",
		label: "New leads",
		empty: "No new leads waiting.",
		icon: "lucide-user-plus",
		tone: "success",
	},
	{
		key: "visits_today",
		label: "Site visits today",
		empty: "No site visits today.",
		icon: "lucide-calendar-check",
		tone: "info",
	},
	{
		key: "visits_tomorrow",
		label: "Tomorrow's visits to confirm",
		empty: "No site visits tomorrow.",
		icon: "lucide-calendar-clock",
		tone: "warning",
	},
];

// The overdue and consent badges of one row.
const TodayBadges = defineComponent({
	props: { row: { type: Object, required: true } },
	setup(props) {
		return () =>
			h("div", { class: "flex flex-wrap gap-1" }, [
				props.row.state === "overdue"
					? h(StatusBadge, {
							tone: "danger",
							label: "Overdue",
							"data-testid": "sellos-today-overdue",
					  })
					: null,
				props.row.consent_warning
					? h(StatusBadge, {
							tone: props.row.consent_warning === "red" ? "danger" : "warning",
							label: props.row.consent_status,
							"data-testid": "sellos-today-consent",
							"data-level": props.row.consent_warning,
							title: props.row.consent_message,
					  })
					: null,
			]);
	},
});

const view = ref(null);
const outcomes = ref([]);
const confirmations = ref([]);
const error = ref("");
const logging = ref(null); // { row, section } while the log drawer is open
const logError = ref("");
const form = reactive({ outcome: "", notes: "", followUp: "" });

const team = computed(() => view.value?.scope === "team");
const scopeNote = computed(() =>
	team.value
		? "Your team's day, by agent."
		: view.value?.scope === "all"
		? "Everyone's day."
		: "Your day."
);

const outcomeOptions = computed(() => [
	{ label: "Choose an outcome", value: "" },
	...outcomes.value.map((o) => ({ label: o.name, value: o.name })),
]);
const chosen = computed(() => outcomes.value.find((o) => o.name === form.outcome));

// A row's own key: a follow up or visit has a name, a new lead only its lead.
const keyed = (rows) => rows.map((row) => ({ ...row, _key: row.name || row.lead }));
const rowsOf = (key) => keyed(view.value[key]);

function columnsFor(key) {
	const second = key === "follow_ups" ? "Follow up" : key === "new_leads" ? "" : "Project";
	return [
		{ key: "lead_title", label: "Lead", primary: true },
		...(second ? [{ key: "detail", label: second, wrap: true }] : []),
		{ key: "when", label: key === "new_leads" ? "Added" : "When" },
		...(team.value || view.value?.scope === "all"
			? [{ key: "agent_name", label: "Agent" }]
			: []),
		{ key: "status", label: "Status", wrap: true },
	];
}

// The row's attributes for specs and the table's own test ids.
function tableProps(key) {
	return {
		testid: `sellos-today-table-${key}`,
		rowTestid: "sellos-today-row",
		actions: (row) => actionsFor(key, row),
		rowName: (row) => row.lead_title,
		rowAttrs: (row) => ({ "data-lead": row.lead, "data-section": key }),
	};
}

// Every row action is in the row menu (docs/DESIGN_SYSTEM.md, "Lists", rule c): call, log, open the lead and,
// on tomorrow's visits, the confirmation.
const router = useRouter();
const calling = ref(null);
const rescheduling = ref(null);
const rescheduleWhen = ref("");
const visitError = ref("");
function actionsFor(section, row) {
	const items = [
		{ label: "Call", onClick: () => (calling.value = row) },
		{ label: "Log a call", onClick: () => startLog(row, section) },
		{ label: "Open lead", onClick: () => router.push(`/crm/leads/${row.lead}`) },
	];
	if (section === "visits_tomorrow" && row.status !== "Done") {
		const labels = {
			"Not confirmed": "Mark not confirmed",
			Confirmed: "Confirm visit",
			Rescheduled: "Reschedule",
			Cancelled: "Cancel visit",
		};
		for (const status of confirmations.value) {
			if (status === row.confirmation_status) continue;
			items.push({
				label: labels[status] || status,
				onClick: () =>
					status === "Rescheduled" ? openReschedule(row) : confirmVisit(row, status),
			});
		}
	}
	return items;
}
function openReschedule(row) {
	visitError.value = "";
	rescheduleWhen.value = "";
	rescheduling.value = row;
}
function closeReschedule() {
	visitError.value = "";
	rescheduling.value = null;
}
async function confirmVisit(row, status) {
	try {
		await crmApi.confirmSiteVisit(row.name, status, null);
	} catch (e) {
		error.value = serverMessage(e, "The confirmation could not be saved.");
	}
	await load();
}
async function reschedule() {
	const row = rescheduling.value;
	if (!row || !rescheduleWhen.value) return;
	visitError.value = "";
	try {
		await crmApi.confirmSiteVisit(row.name, "Rescheduled", rescheduleWhen.value);
		rescheduling.value = null;
	} catch (e) {
		visitError.value = serverMessage(e, "The visit could not be rescheduled.");
		return;
	}
	await load();
}

function whenOf(row) {
	return formatWhen(row.visit_datetime || row.due_at || row.due_date || row.creation || "");
}

// The rows of one list grouped by agent, in the order of the list, and every agent of the team listed
// in name order (an agent with nothing has no group).
function groups(key) {
	const byAgent = new Map();
	for (const row of keyed(view.value[key])) {
		if (!byAgent.has(row.agent))
			byAgent.set(row.agent, { agent: row.agent, agent_name: row.agent_name, rows: [] });
		byAgent.get(row.agent).rows.push(row);
	}
	return [...byAgent.values()].sort((a, b) => a.agent_name.localeCompare(b.agent_name));
}

function startLog(row, section) {
	logError.value = "";
	Object.assign(form, { outcome: "", notes: "", followUp: "" });
	logging.value = { row, section };
}

// On a follow up the call marks it done, on any other row it is logged on the lead.
async function saveLog() {
	logError.value = "";
	const { row, section } = logging.value;
	const values = {
		outcome: form.outcome,
		notes: form.notes,
		follow_up_at: chosen.value?.needs_follow_up ? form.followUp : null,
	};
	try {
		if (section === "follow_ups") await crmApi.completeFollowUp(row.name, values);
		else await crmApi.logCall(row.lead, values);
		logging.value = null;
		await load();
	} catch (e) {
		logError.value = serverMessage(e, "The call could not be logged.");
	}
}

async function load() {
	error.value = "";
	try {
		view.value = await crmApi.todayScreen();
	} catch (e) {
		error.value = serverMessage(e, "Today could not be loaded.");
	}
}

async function init() {
	try {
		const [list, options] = await Promise.all([
			crmApi.listCallOutcomes(),
			crmApi.siteVisitOptions(),
		]);
		outcomes.value = list.outcomes;
		confirmations.value = options.confirmations;
	} catch (e) {
		error.value = serverMessage(e, "Today could not be loaded.");
	}
	await load();
}

const onRetry = init;
onMounted(init);
</script>
