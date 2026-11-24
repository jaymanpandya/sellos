<template>
	<PageTemplate data-testid="sellos-inventory-import-page">
		<template #header>
			<PageHeader
				title="Import inventory"
				text="Bring in your developers, projects, units, properties, listings and mandates from a spreadsheet. Import them in that order, one file for each. A dry run shows what would happen and writes nothing. A record that is already in SellOS is updated, never doubled, so the same file can be imported again safely."
				icon="lucide-file-up"
			/>
		</template>
		<LoadError
			v-if="error"
			class="mb-ui-md"
			data-testid="sellos-inventory-import-error"
			:message="error"
			@retry="start"
		/>

		<ListCard title="What the file holds" class="mb-ui-md">
			<div class="space-y-ui-md">
				<div role="group" aria-label="Record type" class="flex flex-wrap gap-ui-sm">
					<AppButton
						v-for="t in types"
						:key="t.record_type"
						variant="secondary"
						type="button"
						:active="recordType === t.record_type"
						:aria-pressed="recordType === t.record_type"
						:data-testid="`sellos-inventory-import-type-${t.record_type}`"
						@click="changeType(t.record_type)"
					>
						{{ t.label }}
					</AppButton>
				</div>
				<p class="text-sm text-ink-muted" data-testid="sellos-inventory-import-help">
					{{ help }}
				</p>
				<AppButton
					variant="secondary"
					type="button"
					:disabled="busy || !recordType"
					data-testid="sellos-inventory-import-template"
					@click="downloadTemplate"
				>
					Download the template
				</AppButton>
				<FileField
					:key="fileKey"
					label="Filled in CSV file"
					accept=".csv,text/csv,text/plain"
					data-testid="sellos-inventory-import-file"
					@change="chooseFile"
				/>
			</div>
		</ListCard>

		<ListCard
			v-if="dryRun"
			title="Dry run: nothing has been written"
			class="mb-ui-md"
			data-testid="sellos-inventory-import-dry-run"
		>
			<CountCards :counts="dryRun.counts" />
			<p class="mt-ui-md text-sm text-ink" data-testid="sellos-inventory-import-dry-counts">
				{{ summary(dryRun.counts, true) }}
			</p>
			<FailedRows :failed="dryRun.failed" test-id="sellos-inventory-import-dry-failed" />
			<div class="mt-ui-md">
				<AppButton
					variant="primary"
					type="button"
					:disabled="busy || dryRun.counts.rows === dryRun.counts.failed"
					data-testid="sellos-inventory-import-run"
					@click="run"
				>
					Import the file
				</AppButton>
			</div>
		</ListCard>

		<ListCard
			v-if="result"
			title="Import done"
			class="mb-ui-md"
			data-testid="sellos-inventory-import-result"
			role="status"
		>
			<CountCards :counts="result.counts" />
			<p
				class="mt-ui-md font-medium text-ink"
				data-testid="sellos-inventory-import-result-counts"
			>
				{{ summary(result.counts, false) }}
			</p>
			<FailedRows :failed="result.failed" test-id="sellos-inventory-import-failed" />
			<a
				class="ui-link mt-ui-md inline-flex min-h-touch items-center font-medium"
				:href="result.report_file"
				download
				data-testid="sellos-inventory-import-report"
			>
				Download the reconciliation report
			</a>
		</ListCard>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import FileField from "../components/FileField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import { serverMessage } from "../crm/crmApi";
import { importApi } from "../inventory/inventoryApi";
import CountCards from "../inventory/ImportCountCards.vue";
import FailedRows from "../inventory/ImportFailedRows.vue";

// The Company Admin's import of inventory and mandates (SOS-P4-10C). The file is read in the browser and
// sent as text. The dry run writes nothing; the import writes and shows what the server says it did.
const types = ref([]);
const recordType = ref("Developer");
const csvText = ref("");
const dryRun = ref(null);
const result = ref(null);
const error = ref("");
const busy = ref(false);
const fileKey = ref(0);

const typeOptions = computed(() =>
	types.value.map((t) => ({ label: t.label, value: t.record_type }))
);
const help = computed(
	() => types.value.find((t) => t.record_type === recordType.value)?.help || ""
);

async function ask(action, fallback) {
	error.value = "";
	busy.value = true;
	try {
		return await action();
	} catch (e) {
		error.value = serverMessage(e, fallback);
		return null;
	} finally {
		busy.value = false;
	}
}

async function start() {
	const data = await ask(() => importApi.overview(), "The import could not be opened.");
	if (data) types.value = data.types;
}
onMounted(start);

function changeType(type) {
	recordType.value = type;
	csvText.value = "";
	dryRun.value = null;
	result.value = null;
	fileKey.value += 1;
}

async function downloadTemplate() {
	const data = await ask(
		() => importApi.template(recordType.value),
		"The template could not be made."
	);
	if (!data) return;
	const link = document.createElement("a");
	link.href = URL.createObjectURL(new Blob([data.csv], { type: "text/csv" }));
	link.download = data.file_name;
	link.click();
	URL.revokeObjectURL(link.href);
}

async function chooseFile(event) {
	const file = event.target.files?.[0];
	if (!file) return;
	result.value = null;
	csvText.value = await file.text();
	dryRun.value = await ask(
		() => importApi.preview(recordType.value, csvText.value),
		"The file could not be read."
	);
}

async function run() {
	const data = await ask(
		() => importApi.run(recordType.value, csvText.value),
		"The import failed."
	);
	if (data) {
		result.value = data;
		dryRun.value = null;
		csvText.value = "";
	}
}

function summary(c, would) {
	const verb = would ? ["would be created", "would be updated"] : ["created", "updated"];
	return (
		`${c.rows} rows: ${c.created} ${verb[0]}, ${c.updated} ${verb[1]}, ${c.unchanged} unchanged, ` +
		`${c.merged} merged into another row of the file, ${c.failed} failed.`
	);
}
</script>
