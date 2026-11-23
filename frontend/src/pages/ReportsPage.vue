<template>
	<div data-testid="sellos-reports-page">
		<PageHeader
			title="Reports"
			text="Choose a report and the dates. Every figure opens the records behind it. You see the records you may see."
			icon="lucide-chart-column"
		/>
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
		<template v-else>
			<FilterBar
				apply-label="Show report"
				clear-label="Last 30 days"
				@apply="load"
				@clear="reset"
			>
				<FormField
					v-model="key"
					type="select"
					label="Report"
					:options="reports.map((r) => ({ label: r.title, value: r.key }))"
					data-testid="sellos-reports-report"
				/>
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
			</FilterBar>
			<ListCard title="Saved views" class="mb-ui-md">
				<div class="grid gap-ui-md md:grid-cols-3">
					<FormField
						v-model="viewKey"
						type="select"
						label="Open a saved view"
						:options="viewOptions"
						data-testid="sellos-reports-view"
					/>
					<FormField
						v-model="viewName"
						label="Name for this view"
						data-testid="sellos-reports-view-name"
					/>
					<div class="flex flex-col justify-end gap-ui-xs">
						<FormField
							v-model="viewShared"
							type="checkbox"
							label="Share with everyone who may read this report"
							data-testid="sellos-reports-view-shared"
						/>
						<FormField
							v-model="viewRelative"
							type="checkbox"
							label="Always the same number of days, ending today"
							data-testid="sellos-reports-view-relative"
						/>
					</div>
				</div>
				<div class="mt-ui-sm flex flex-wrap items-center gap-ui-sm">
					<AppButton data-testid="sellos-reports-view-save" @click="saveView">
						Save view
					</AppButton>
					<AppButton
						v-if="chosenView && (chosenView.mine || canExport)"
						variant="danger"
						data-testid="sellos-reports-view-delete"
						@click="deleteView"
					>
						Delete view
					</AppButton>
					<span class="text-sm text-ink-muted" data-testid="sellos-reports-view-note">{{
						viewNote
					}}</span>
				</div>
			</ListCard>
			<ListCard v-if="canExport" title="Export" class="mb-ui-md">
				<p class="mb-ui-sm text-sm text-ink-muted">
					Exports the rows and figures on this screen, for these dates. Every export is
					logged.
				</p>
				<div class="flex flex-wrap items-center gap-ui-sm">
					<AppButton data-testid="sellos-reports-export-csv" @click="exportFile('csv')">
						Export CSV
					</AppButton>
					<AppButton data-testid="sellos-reports-export-pdf" @click="exportFile('pdf')">
						Export PDF
					</AppButton>
					<span
						class="text-sm text-ink-muted"
						data-testid="sellos-reports-export-note"
						>{{ exportNote }}</span
					>
				</div>
			</ListCard>
			<ListCard v-if="canExport && schedules" title="Email schedules" class="mb-ui-md">
				<p v-if="!schedules.mail_ready" class="mb-ui-sm text-sm text-ink-muted">
					This site cannot send email yet, so a schedule is kept but nothing is sent.
				</p>
				<table
					v-if="schedules.schedules.length"
					class="mb-ui-md w-full text-left text-sm"
					data-testid="sellos-reports-schedules"
				>
					<thead class="text-xs text-ink-muted">
						<tr>
							<th scope="col" class="py-ui-sm">Name</th>
							<th scope="col">Report</th>
							<th scope="col">When</th>
							<th scope="col">Next</th>
							<th scope="col">Last result</th>
							<th scope="col"><span class="sr-only">Actions</span></th>
						</tr>
					</thead>
					<tbody class="divide-y divide-line-soft">
						<tr
							v-for="item in schedules.schedules"
							:key="item.name"
							data-testid="sellos-reports-schedule"
							:data-schedule="item.name"
							class="text-ink"
						>
							<td class="py-ui-sm">{{ item.title }}</td>
							<td>{{ item.report_title }}</td>
							<td>{{ whenText(item) }}</td>
							<td>{{ item.next_run ? item.next_run.slice(0, 16) : "Off" }}</td>
							<td data-col="result">{{ item.last_result || "Not sent yet" }}</td>
							<td class="flex gap-ui-xs py-ui-xs">
								<AppButton
									data-testid="sellos-reports-schedule-send"
									@click="sendSchedule(item)"
								>
									Send now
								</AppButton>
								<AppButton
									variant="danger"
									data-testid="sellos-reports-schedule-delete"
									@click="deleteSchedule(item)"
								>
									Delete
								</AppButton>
							</td>
						</tr>
					</tbody>
				</table>
				<div class="grid gap-ui-md md:grid-cols-3">
					<FormField
						v-model="plan.title"
						label="Name of the schedule"
						data-testid="sellos-reports-schedule-title"
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
				</div>
				<p class="mb-ui-xs mt-ui-md text-sm text-ink-muted">
					Who gets it. Each person is sent the report with only the records they may see.
				</p>
				<div class="flex flex-wrap gap-ui-md">
					<FormField
						v-for="person in schedules.people"
						:key="person.email"
						type="checkbox"
						:label="person.name"
						:model-value="plan.recipients.includes(person.email)"
						:value="person.email"
						data-testid="sellos-reports-schedule-person"
						@update:model-value="togglePerson(person.email, $event)"
					/>
				</div>
				<div class="mt-ui-sm flex flex-wrap items-center gap-ui-sm">
					<AppButton
						variant="primary"
						data-testid="sellos-reports-schedule-save"
						@click="saveSchedule"
					>
						Schedule this report
					</AppButton>
					<span
						class="text-sm text-ink-muted"
						data-testid="sellos-reports-schedule-note"
						>{{ scheduleNote }}</span
					>
				</div>
			</ListCard>
			<LoadingSkeleton v-if="!result" />
			<template v-else>
				<p class="mb-ui-xs text-sm text-ink-muted" data-testid="sellos-reports-about">
					{{ result.report.description }} {{ result.report.date_label }} from
					{{ result.from_date }} to {{ result.to_date }}.
				</p>
				<p class="mb-ui-md text-sm text-ink-muted" data-testid="sellos-reports-scope">
					{{ scopeText }}
					<span
						v-if="result.report.last_refreshed"
						data-testid="sellos-reports-refreshed"
					>
						Summary table refreshed {{ result.report.last_refreshed.slice(0, 16) }}.
					</span>
					<AppButton
						v-if="canRefresh"
						class="ml-ui-sm"
						data-testid="sellos-reports-refresh"
						@click="refresh"
					>
						Refresh summary table
					</AppButton>
				</p>
				<div class="mb-ui-md grid grid-cols-2 gap-ui-md md:grid-cols-3">
					<div>
						<StatCard
							:label="result.report.measure_label"
							:value="show(result.report.unit, grand)"
							:note="`${result.totals.count} records`"
							icon="lucide-sigma"
							value-testid="sellos-reports-total"
						/>
						<AppButton
							class="mt-ui-sm w-full"
							data-testid="sellos-reports-open-all"
							@click="open('All records', undefined)"
						>
							See records
						</AppButton>
					</div>
				</div>
				<ListCard
					:title="`By ${result.report.group_label.toLowerCase()}`"
					class="mb-ui-md"
				>
					<EmptyState
						v-if="!result.rows.length"
						title="Nothing in these dates"
						text="No record falls between these dates. Choose other dates."
						icon="lucide-chart-column"
					/>
					<table
						v-else
						class="w-full text-left text-sm"
						data-testid="sellos-reports-rows"
					>
						<thead class="text-xs text-ink-muted">
							<tr>
								<th scope="col" class="py-ui-sm">
									{{ result.report.group_label }}
								</th>
								<th scope="col">Records</th>
								<th v-if="isSum" scope="col">{{ result.report.measure_label }}</th>
								<th scope="col"><span class="sr-only">Records</span></th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							<tr
								v-for="row in result.rows"
								:key="row.group"
								data-testid="sellos-reports-row"
								:data-group="row.group"
								class="text-ink"
							>
								<td class="py-ui-sm">{{ row.label }}</td>
								<td class="tabular-nums" data-col="count">{{ row.count }}</td>
								<td v-if="isSum" class="tabular-nums" data-col="total">
									{{ show(result.report.unit, row.total) }}
								</td>
								<td>
									<AppButton
										data-testid="sellos-reports-open"
										@click="open(row.label, row.group)"
									>
										Records
									</AppButton>
								</td>
							</tr>
						</tbody>
					</table>
				</ListCard>
				<ListCard v-if="drill" :title="drill.title" class="mb-ui-md">
					<div data-testid="sellos-reports-drill" :data-count="drill.total">
						<p
							class="mb-ui-sm text-sm text-ink-muted"
							data-testid="sellos-reports-drill-total"
						>
							{{ drill.total }} records<span v-if="drill.truncated">
								, the newest {{ drill.shown }} are listed</span
							>.
						</p>
						<EmptyState
							v-if="!drill.records.length"
							title="No records"
							text="No record matches this figure."
							icon="lucide-file-search"
						/>
						<table v-else class="w-full text-left text-sm">
							<thead class="text-xs text-ink-muted">
								<tr>
									<th
										v-for="(column, at) in drill.columns"
										:key="column.field"
										scope="col"
										:class="at === 0 ? 'py-ui-sm' : ''"
									>
										{{ column.label }}
									</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-line-soft">
								<tr
									v-for="record in drill.records"
									:key="record.name"
									data-testid="sellos-reports-record"
									:data-record="record.name"
									class="text-ink"
								>
									<td
										v-for="(column, at) in drill.columns"
										:key="column.field"
										:class="at === 0 ? 'py-ui-sm' : ''"
									>
										<router-link
											v-if="column.field === leadColumn && record.lead"
											class="text-brand underline"
											:to="`/crm/leads/${record.lead}`"
										>
											{{ cell(column.field, record.values[at]) }}
										</router-link>
										<span v-else>{{
											cell(column.field, record.values[at])
										}}</span>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</ListCard>
			</template>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import FilterBar from "../components/FilterBar.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import StatCard from "../components/StatCard.vue";
import { serverMessage } from "../crm/crmApi";
import { rupees, talkTime } from "../reports/callsApi";
import { exportsApi, reportsApi, saveFile } from "../reports/engineApi";

const reports = ref(null);
const scope = ref("own");
const key = ref("");
const range = reactive({ from_date: "", to_date: "" });
const result = ref(null);
const drill = ref(null);
const error = ref("");

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
		return value.slice(0, 16);
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
		range.from_date = result.value.from_date;
		range.to_date = result.value.to_date;
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

function whenText(item) {
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
		scheduleNote.value = `Scheduled ${saved.title}. Next delivery ${saved.next_run.slice(
			0,
			16
		)}.`;
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
