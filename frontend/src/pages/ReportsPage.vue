<template>
	<PageTemplate data-testid="sellos-reports-page">
		<template #header>
			<PageHeader
				title="Reports"
				text="Choose a report and the dates. Every figure opens the records behind it. You see the records you may see."
				icon="lucide-chart-column"
			>
				<template v-if="reports && reports.length">
					<template v-if="canExport">
						<AppButton
							data-testid="sellos-reports-export-csv"
							@click="exportFile('csv')"
						>
							Export CSV
						</AppButton>
						<AppButton
							data-testid="sellos-reports-export-pdf"
							@click="exportFile('pdf')"
						>
							Export PDF
						</AppButton>
						<AppButton
							v-if="schedules"
							type="button"
							data-testid="sellos-reports-schedule-new"
							@click="scheduling = true"
						>
							Schedule report
						</AppButton>
					</template>
					<AppButton
						v-if="chosenView && (chosenView.mine || canExport)"
						variant="danger"
						data-testid="sellos-reports-view-delete"
						@click="deleteView"
					>
						Delete view
					</AppButton>
					<AppButton
						type="button"
						variant="primary"
						data-testid="sellos-reports-view-new"
						@click="savingView = true"
					>
						Save view
					</AppButton>
				</template>
			</PageHeader>
		</template>

		<template v-if="result" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-reports-stats" />
		</template>

		<template v-if="reports && reports.length" #filters>
			<FilterBar
				v-model:open="moreOpen"
				hide-search
				apply-label="Show report"
				clear-label="Last 30 days"
				more-testid="sellos-reports-filters-toggle"
				:active="datesChanged"
				data-testid="sellos-reports-filters"
				@apply="load"
				@clear="reset"
			>
				<FormField
					v-model="key"
					compact
					type="select"
					label="Report"
					:options="reports.map((r) => ({ label: r.title, value: r.key }))"
					data-testid="sellos-reports-report"
				/>
				<FormField
					v-model="viewKey"
					compact
					type="select"
					label="Open a saved view"
					:options="viewOptions"
					data-testid="sellos-reports-view"
				/>
				<template #more>
					<FormField
						v-model="range.from_date"
						type="date"
						label="From"
						data-testid="sellos-reports-from"
					/>
					<FormField
						v-model="range.to_date"
						type="date"
						label="To"
						data-testid="sellos-reports-to"
					/>
				</template>
			</FilterBar>
		</template>

		<div v-if="error" data-testid="sellos-reports-error">
			<LoadError :message="error" @retry="start" />
		</div>
		<LoadingSkeleton v-else-if="!reports" />
		<EmptyState
			v-else-if="!reports.length"
			title="No reports for you"
			text="No report has been made visible to your role."
			icon="lucide-chart-column"
		/>
		<div v-else class="space-y-ui-md">
			<p
				v-if="!savingView && viewNote"
				class="text-sm text-ink-muted"
				data-testid="sellos-reports-view-note"
			>
				{{ viewNote }}
			</p>
			<p
				v-if="exportNote"
				class="text-sm text-ink-muted"
				data-testid="sellos-reports-export-note"
			>
				{{ exportNote }}
			</p>
			<LoadingSkeleton v-if="!result" />
			<template v-else>
				<section class="ui-card flex flex-wrap items-center justify-between gap-ui-md">
					<div class="min-w-0 text-sm text-ink-muted">
						<p data-testid="sellos-reports-about">
							{{ result.report.description }} {{ result.report.date_label }} from
							{{ result.from_date }} to {{ result.to_date }}.
						</p>
						<p data-testid="sellos-reports-scope">
							{{ scopeText }}
							<span
								v-if="result.report.last_refreshed"
								data-testid="sellos-reports-refreshed"
							>
								Summary table refreshed
								{{ formatDateTime(result.report.last_refreshed) }}.
							</span>
						</p>
					</div>
					<div class="flex flex-wrap items-center gap-ui-sm">
						<AppButton
							v-if="canRefresh"
							data-testid="sellos-reports-refresh"
							@click="refresh"
						>
							Refresh summary table
						</AppButton>
						<AppButton
							data-testid="sellos-reports-open-all"
							@click="open('All records', undefined)"
						>
							See records
						</AppButton>
					</div>
				</section>

				<DataTable
					:title="`By ${result.report.group_label.toLowerCase()}`"
					:columns="groupColumns"
					:rows="result.rows"
					row-key="group"
					:row-attrs="(row) => ({ 'data-group': row.group })"
					:page-size="200"
					empty-title="Nothing in these dates"
					empty-text="No record falls between these dates. Choose other dates."
					empty-icon="lucide-chart-column"
					testid="sellos-reports-rows"
					row-testid="sellos-reports-row"
					empty-testid="sellos-reports-rows-empty"
				>
					<template #cell-count="{ row }">
						<span class="tabular-nums" data-col="count">{{ row.count }}</span>
					</template>
					<template #cell-total="{ row }">
						<span class="tabular-nums" data-col="total">{{
							show(result.report.unit, row.total)
						}}</span>
					</template>
					<template #cell-open="{ row }">
						<AppButton
							data-testid="sellos-reports-open"
							@click="open(row.label, row.group)"
						>
							Records
						</AppButton>
					</template>
				</DataTable>

				<div v-if="drill" data-testid="sellos-reports-drill" :data-count="drill.total">
					<p
						class="mb-ui-sm text-sm text-ink-muted"
						data-testid="sellos-reports-drill-total"
					>
						{{ drill.total }} records<span v-if="drill.truncated">
							, the newest {{ drill.shown }} are listed</span
						>.
					</p>
					<DataTable
						:title="drill.title"
						:columns="drillColumns"
						:rows="drillRows"
						row-key="name"
						:row-attrs="(row) => ({ 'data-record': row.name })"
						:page-size="200"
						empty-title="No records"
						empty-text="No record matches this figure."
						empty-icon="lucide-file-search"
						testid="sellos-reports-drill-table"
						row-testid="sellos-reports-record"
						empty-testid="sellos-reports-drill-empty"
					>
						<template
							v-for="(column, at) in drill.columns"
							:key="column.field"
							#[drillSlot(at)]="{ row }"
						>
							<router-link
								v-if="column.field === leadColumn && row.lead"
								class="text-brand underline"
								:to="`/crm/leads/${row.lead}`"
							>
								{{ row[drillKey(at)] }}
							</router-link>
							<span v-else>{{ row[drillKey(at)] }}</span>
						</template>
					</DataTable>
				</div>
			</template>

			<div v-if="canExport && schedules" class="space-y-ui-sm">
				<p v-if="!schedules.mail_ready" class="text-sm text-ink-muted">
					This site cannot send email yet, so a schedule is kept but nothing is sent.
				</p>
				<p
					v-if="!scheduling && scheduleNote"
					class="text-sm text-ink-muted"
					data-testid="sellos-reports-schedule-note"
				>
					{{ scheduleNote }}
				</p>
				<DataTable
					title="Email schedules"
					:columns="scheduleColumns"
					:rows="schedules.schedules"
					row-key="name"
					:row-attrs="(row) => ({ 'data-schedule': row.name })"
					empty-title="No schedule yet"
					empty-text="Schedule this report to be emailed to the people you choose."
					empty-icon="lucide-calendar-clock"
					testid="sellos-reports-schedules"
					row-testid="sellos-reports-schedule"
					empty-testid="sellos-reports-schedules-empty"
				>
					<template #cell-when="{ row }">{{ whenLabel(row) }}</template>
					<template #cell-next_run="{ row }">{{
						row.next_run ? formatDateTime(row.next_run) : "Off"
					}}</template>
					<template #cell-last_result="{ row }">
						<span data-col="result">{{ row.last_result || "Not sent yet" }}</span>
					</template>
					<template #cell-actions="{ row }">
						<div class="flex gap-ui-xs">
							<AppButton
								data-testid="sellos-reports-schedule-send"
								@click="sendSchedule(row)"
							>
								Send now
							</AppButton>
							<AppButton
								variant="danger"
								data-testid="sellos-reports-schedule-delete"
								@click="deleteSchedule(row)"
							>
								Delete
							</AppButton>
						</div>
					</template>
				</DataTable>
			</div>
		</div>

		<!-- Saving a view is a drawer, not a form under the report. -->
		<FormDrawer
			:open="savingView"
			title="Save this view"
			text="The report and the dates you are looking at."
			submit-label="Save view"
			testid="sellos-reports-view-form"
			submit-testid="sellos-reports-view-save"
			cancel-testid="sellos-reports-view-cancel"
			@close="savingView = false"
			@submit="saveView"
		>
			<FormSection title="View">
				<FormField
					v-model="viewName"
					label="Name for this view"
					data-testid="sellos-reports-view-name"
					class="md:col-span-2"
				/>
				<FormField
					v-model="viewShared"
					type="checkbox"
					label="Share with everyone who may read this report"
					data-testid="sellos-reports-view-shared"
					class="md:col-span-2"
				/>
				<FormField
					v-model="viewRelative"
					type="checkbox"
					label="Always the same number of days, ending today"
					data-testid="sellos-reports-view-relative"
					class="md:col-span-2"
				/>
			</FormSection>
			<p
				v-if="viewNote"
				class="text-sm text-ink-muted"
				data-testid="sellos-reports-view-note"
			>
				{{ viewNote }}
			</p>
		</FormDrawer>

		<FormDrawer
			v-if="canExport && schedules"
			:open="scheduling"
			title="Schedule this report"
			text="Emailed to the people you choose, each with only the records they may see."
			submit-label="Schedule this report"
			testid="sellos-reports-schedule-form"
			submit-testid="sellos-reports-schedule-save"
			cancel-testid="sellos-reports-schedule-cancel"
			@close="scheduling = false"
			@submit="saveSchedule"
		>
			<FormSection title="When">
				<FormField
					v-model="plan.title"
					label="Name of the schedule"
					data-testid="sellos-reports-schedule-title"
					class="md:col-span-2"
				/>
				<FormField
					v-model="plan.frequency"
					type="select"
					label="How often"
					:options="['Daily', 'Weekly', 'Monthly']"
					data-testid="sellos-reports-schedule-frequency"
				/>
				<FormField
					v-if="plan.frequency === 'Weekly'"
					v-model="plan.weekday"
					type="select"
					label="Day of the week"
					:options="WEEKDAYS"
					data-testid="sellos-reports-schedule-weekday"
				/>
				<FormField
					v-if="plan.frequency === 'Monthly'"
					v-model="plan.day_of_month"
					type="number"
					label="Day of the month (1 to 28)"
					data-testid="sellos-reports-schedule-day"
				/>
				<FormField
					v-model="plan.send_hour"
					type="number"
					label="Hour of the day (0 to 23)"
					data-testid="sellos-reports-schedule-hour"
				/>
				<FormField
					v-model="plan.range_days"
					type="number"
					label="Days covered, ending yesterday"
					data-testid="sellos-reports-schedule-days"
				/>
				<FormField
					v-model="plan.file_format"
					type="select"
					label="Attachment"
					:options="['PDF', 'CSV']"
					data-testid="sellos-reports-schedule-format"
				/>
			</FormSection>
			<FormSection title="Who gets it">
				<FormField
					v-for="person in schedules ? schedules.people : []"
					:key="person.email"
					type="checkbox"
					:label="person.name"
					:model-value="plan.recipients.includes(person.email)"
					:value="person.email"
					data-testid="sellos-reports-schedule-person"
					@update:model-value="togglePerson(person.email, $event)"
				/>
			</FormSection>
			<p
				v-if="scheduleNote"
				class="text-sm text-ink-muted"
				data-testid="sellos-reports-schedule-note"
			>
				{{ scheduleNote }}
			</p>
		</FormDrawer>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";

import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import EmptyState from "../components/EmptyState.vue";
import FilterBar from "../components/FilterBar.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import { serverMessage } from "../crm/crmApi";
import { formatDateTime } from "../format";
import { rupees, talkTime } from "../reports/callsApi";
import { exportsApi, reportsApi, saveFile } from "../reports/engineApi";

const reports = ref(null);
const scope = ref("own");
const key = ref("");
const range = reactive({ from_date: "", to_date: "" });
const result = ref(null);
const drill = ref(null);
const error = ref("");
// The dates are the one filter here, so the panel that holds them starts open.
const moreOpen = ref(true);
const savingView = ref(false);
const scheduling = ref(false);
// The dates the report opened with, so Clear shows only when they have been changed.
const defaults = reactive({ from_date: "", to_date: "" });
const datesChanged = computed(
	() =>
		Boolean(defaults.from_date) &&
		(range.from_date !== defaults.from_date || range.to_date !== defaults.to_date)
);

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const views = ref([]);
const viewKey = ref("none");
const viewName = ref("");
const viewShared = ref(false);
const viewRelative = ref(false);
const viewNote = ref("");
const exportNote = ref("");
const schedules = ref(null);
const scheduleNote = ref("");
const plan = reactive(blankPlan());

function blankPlan() {
	return {
		title: "",
		frequency: "Weekly",
		weekday: "Monday",
		day_of_month: 1,
		send_hour: 8,
		range_days: 7,
		file_format: "PDF",
		recipients: [],
	};
}

const viewOptions = computed(() => [
	{ label: "No saved view", value: "none" },
	...views.value.map((v) => ({
		label: `${v.title} (${v.report_title}${v.mine ? "" : `, shared by ${v.owner_name}`})`,
		value: v.name,
	})),
]);
const chosenView = computed(() => views.value.find((v) => v.name === viewKey.value));

const isSum = computed(() => result.value?.report.measure === "Sum");
const grand = computed(() =>
	isSum.value ? result.value.totals.total : result.value.totals.count
);
const canRefresh = computed(() => scope.value === "all");
const canExport = computed(() => scope.value === "all");
const scopeText = computed(
	() =>
		({
			all: "All records of the company.",
			team: "Your team's records only.",
			own: "Your own records only.",
		}[scope.value] || "")
);
// The column that holds the lead's name opens the lead.
const leadColumn = computed(
	() => drill.value?.columns.find((c) => ["lead", "lead_title"].includes(c.field))?.field
);

const kpis = computed(() => {
	const r = result.value;
	const items = [
		{
			label: r.report.measure_label,
			value: show(r.report.unit, grand.value),
			caption: `${r.totals.count} records`,
			icon: "lucide-sigma",
			valueTestid: "sellos-reports-total",
		},
	];
	if (isSum.value) {
		items.push({
			label: "Records",
			value: r.totals.count,
			caption: "In these dates",
			icon: "lucide-file-search",
		});
	}
	items.push({
		label: r.report.group_label,
		value: r.rows.length,
		caption: "Rows below",
		icon: "lucide-rows-3",
	});
	return items;
});

const groupColumns = computed(() => [
	{ key: "label", label: result.value.report.group_label, primary: true },
	{ key: "count", label: "Records", align: "right" },
	...(isSum.value
		? [{ key: "total", label: result.value.report.measure_label, align: "right" }]
		: []),
	{ key: "open", label: "" },
]);

// The records behind a figure: one column for each the server names.
const drillKey = (at) => `c${at}`;
const drillSlot = (at) => `cell-${drillKey(at)}`;
const drillColumns = computed(() =>
	drill.value.columns.map((c, at) => ({ key: drillKey(at), label: c.label, primary: at === 0 }))
);
const drillRows = computed(() =>
	drill.value.records.map((record) => ({
		name: record.name,
		lead: record.lead,
		...Object.fromEntries(
			drill.value.columns.map((c, at) => [drillKey(at), cell(c.field, record.values[at])])
		),
	}))
);

const scheduleColumns = [
	{ key: "title", label: "Name", primary: true },
	{ key: "report_title", label: "Report" },
	{ key: "when", label: "When" },
	{ key: "next_run", label: "Next" },
	{ key: "last_result", label: "Last result" },
	{ key: "actions", label: "" },
];

function show(unit, value) {
	if (unit === "rupees") return rupees(value);
	if (unit === "seconds") return talkTime(value);
	return Number(value || 0).toLocaleString("en-IN");
}

const RUPEE_FIELDS = [
	"cost_rupees",
	"price",
	"commission_amount",
	"commission_due",
	"asking_price",
	"budget_to",
];

function cell(field, value) {
	if (RUPEE_FIELDS.includes(field)) return rupees(value);
	if (field === "duration") return talkTime(value);
	if (typeof value === "string" && /^\d{4}-\d\d-\d\d \d\d:\d\d/.test(value))
		return formatDateTime(value);
	return value ?? "";
}

async function start() {
	error.value = "";
	try {
		const found = await reportsApi.list();
		scope.value = found.scope;
		reports.value = found.reports.filter((r) => r.enabled);
		if (reports.value.length) key.value = reports.value[0].key;
	} catch (e) {
		error.value = serverMessage(e, "The reports could not be loaded.");
	}
}

async function load() {
	if (!key.value) return;
	error.value = "";
	drill.value = null;
	try {
		result.value = await reportsApi.run(key.value, { ...range });
		const fresh = !range.from_date && !range.to_date;
		range.from_date = result.value.from_date;
		range.to_date = result.value.to_date;
		if (fresh || !defaults.from_date) {
			defaults.from_date = range.from_date;
			defaults.to_date = range.to_date;
		}
	} catch (e) {
		error.value = serverMessage(e, "The report could not be loaded.");
	}
}

function reset() {
	range.from_date = "";
	range.to_date = "";
	load();
}

// The records behind a figure, for the dates the report shows (not for dates typed since).
async function open(title, group) {
	try {
		const found = await reportsApi.records(
			result.value.report.key,
			{ from_date: result.value.from_date, to_date: result.value.to_date },
			group
		);
		drill.value = { title, ...found };
	} catch (e) {
		error.value = serverMessage(e, "The records could not be loaded.");
	}
}

async function refresh() {
	try {
		await reportsApi.refresh(result.value.report.key);
		await load();
	} catch (e) {
		error.value = serverMessage(e, "The summary table could not be refreshed.");
	}
}

async function loadViews() {
	try {
		views.value = (await exportsApi.views()).views;
	} catch (e) {
		viewNote.value = serverMessage(e, "The saved views could not be loaded.");
	}
}

async function loadSchedules() {
	if (!canExport.value) return;
	try {
		schedules.value = await exportsApi.schedules();
	} catch (e) {
		scheduleNote.value = serverMessage(e, "The schedules could not be loaded.");
	}
}

// Opening a view sets the report and the dates it holds and shows the report, read with the reader's own scope.
let opening = false;
watch(viewKey, async (name) => {
	const view = views.value.find((v) => v.name === name);
	if (!view) return;
	opening = true;
	range.from_date = view.from_date;
	range.to_date = view.to_date;
	viewName.value = view.title;
	viewShared.value = view.shared;
	viewRelative.value = view.range_days > 0;
	if (key.value === view.report) await load();
	else key.value = view.report;
});

// The number of days the dates cover, both end days included.
function daysCovered() {
	const from = new Date(range.from_date || result.value.from_date);
	const to = new Date(range.to_date || result.value.to_date);
	return Math.round((to - from) / 86400000) + 1;
}

async function saveView() {
	viewNote.value = "";
	if (!viewName.value.trim()) {
		viewNote.value = "Give the view a name.";
		return;
	}
	try {
		const values = {
			title: viewName.value,
			report: key.value,
			shared: viewShared.value ? 1 : 0,
			agent: "",
			...(viewRelative.value
				? { range_days: daysCovered() }
				: {
						range_days: 0,
						from_date: range.from_date || result.value?.from_date,
						to_date: range.to_date || result.value?.to_date,
				  }),
		};
		const mine = chosenView.value?.mine ? chosenView.value.name : undefined;
		const saved = await exportsApi.saveView(values, mine);
		await loadViews();
		viewKey.value = saved.name;
		viewNote.value = `Saved the view ${saved.title}.`;
		savingView.value = false;
	} catch (e) {
		viewNote.value = serverMessage(e, "The view could not be saved.");
	}
}

async function deleteView() {
	try {
		const name = viewKey.value;
		await exportsApi.deleteView(name);
		viewKey.value = "none";
		await loadViews();
		viewNote.value = "Deleted the view.";
	} catch (e) {
		viewNote.value = serverMessage(e, "The view could not be deleted.");
	}
}

async function exportFile(format) {
	exportNote.value = "";
	try {
		const made = await exportsApi.exportReport(
			result.value.report.key,
			{ from_date: result.value.from_date, to_date: result.value.to_date },
			format
		);
		saveFile(made);
		exportNote.value = `Exported ${made.filename}: ${made.rows.length} rows, total ${made.totals.count} records.`;
	} catch (e) {
		exportNote.value = serverMessage(e, "The report could not be exported.");
	}
}

function togglePerson(email, on) {
	const rest = plan.recipients.filter((r) => r !== email);
	plan.recipients = on ? [...rest, email] : rest;
}

function whenLabel(item) {
	const at = `${String(item.send_hour).padStart(2, "0")}:00`;
	if (item.frequency === "Weekly") return `Every ${item.weekday} at ${at}`;
	if (item.frequency === "Monthly") return `On day ${item.day_of_month} at ${at}`;
	return `Every day at ${at}`;
}

async function saveSchedule() {
	scheduleNote.value = "";
	try {
		const saved = await exportsApi.saveSchedule({
			...plan,
			report: key.value,
			day_of_month: Number(plan.day_of_month),
			send_hour: Number(plan.send_hour),
			range_days: Number(plan.range_days),
		});
		Object.assign(plan, blankPlan());
		await loadSchedules();
		scheduleNote.value = `Scheduled ${saved.title}. Next delivery ${formatDateTime(
			saved.next_run
		)}.`;
		scheduling.value = false;
	} catch (e) {
		scheduleNote.value = serverMessage(e, "The schedule could not be saved.");
	}
}

async function sendSchedule(item) {
	scheduleNote.value = "";
	try {
		const done = await exportsApi.sendSchedule(item.name);
		await loadSchedules();
		const sent = Object.values(done.results).filter((r) => r === "Sent").length;
		scheduleNote.value = `${item.title}: ${sent} of ${Object.keys(done.results).length} sent.`;
	} catch (e) {
		scheduleNote.value = serverMessage(e, "The report could not be sent.");
	}
}

async function deleteSchedule(item) {
	try {
		await exportsApi.deleteSchedule(item.name);
		await loadSchedules();
		scheduleNote.value = `Deleted ${item.title}.`;
	} catch (e) {
		scheduleNote.value = serverMessage(e, "The schedule could not be deleted.");
	}
}

watch(key, () => {
	result.value = null;
	// A view opens its own report: keep the dates it set.
	if (opening) range.from_date = chosenView.value?.from_date ?? range.from_date;
	opening = false;
	load();
});
onMounted(async () => {
	await start();
	await Promise.all([loadViews(), loadSchedules()]);
});
</script>
