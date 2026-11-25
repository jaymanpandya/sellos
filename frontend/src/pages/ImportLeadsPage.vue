<template>
	<PageTemplate shape="form" data-testid="sellos-import-page">
		<template #header>
			<PageHeader
				title="Import a bought lead list"
				text="Choose a CSV file of a bought lead list, check the preview, then import."
				icon="lucide-file-up"
			/>
		</template>

		<template #notice>
			<Notice title="How the import works">
				<ul>
					<li>
						Every lead comes in from the source Bought list with the consent status
						Unknown, or Registered DND when the file says the number is on the do not
						call list.
					</li>
					<li>A person already in SellOS, or twice in the file, is merged into one.</li>
					<li>Nothing here stops a call or a message: the warning shows on the lead.</li>
				</ul>
			</Notice>
		</template>

		<template v-if="preview" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-import-kpis" />
		</template>

		<LoadError
			v-if="error"
			data-testid="sellos-import-error"
			:message="error"
			@retry="retry"
		/>

		<SectionCard title="The file">
			<FieldGrid>
				<FileField
					label="CSV file"
					accept=".csv,text/csv,text/plain"
					data-testid="sellos-import-file"
					@change="chooseFile"
				/>
				<FormField
					v-model="listName"
					label="Name of the list"
					placeholder="For example Magicbricks Pune, November"
					data-testid="sellos-import-list-name"
				/>
			</FieldGrid>
		</SectionCard>

		<div v-if="preview" class="space-y-4" data-testid="sellos-import-preview">
			<SectionCard title="Which column is which">
				<FieldGrid>
					<FormField
						v-for="f in preview.fields"
						:key="f.field"
						:model-value="mapping[f.field]"
						type="select"
						:label="f.label"
						:options="columnOptions"
						:data-testid="`sellos-import-map-${f.field}`"
						@update:model-value="mapColumn(f.field, $event)"
					/>
				</FieldGrid>

				<p class="mt-ui-md ui-text-small" data-testid="sellos-import-counts">
					{{ preview.counts.rows }} rows: {{ preview.counts.new_leads }} new leads,
					{{ preview.counts.merged_with_existing }} merged with people already in SellOS,
					{{ preview.counts.merged_in_file }} merged within the file,
					{{ preview.counts.registered_dnd }} on the do not call list,
					{{ preview.counts.skipped }} skipped.
				</p>
				<p v-if="preview.counts.unrecognised_dnd" class="ui-text-muted">
					{{ preview.counts.unrecognised_dnd }} do not call values were not recognised
					and are treated as no result.
				</p>
			</SectionCard>

			<DataTable
				title="A sample of the rows"
				caption="A sample of the rows"
				:columns="sampleColumns"
				:rows="preview.sample"
				row-key="rows"
				:row-name="(r) => `row ${r.rows}`"
				empty-title="No rows"
				testid="sellos-import-sample"
				row-testid="sellos-import-sample-row"
			>
				<template #cell-action="{ row }">{{ actions[row.action] }}</template>
			</DataTable>
			<SectionCard title="Skipped rows and import">
				<ul
					v-if="preview.skipped.length"
					class="mt-ui-sm ui-text-muted"
					data-testid="sellos-import-skipped"
				>
					<li v-for="s in preview.skipped" :key="s.row">
						Row {{ s.row }}: {{ s.reason }}
					</li>
				</ul>
				<div class="mt-ui-md">
					<AppButton
						variant="primary"
						type="button"
						:disabled="busy || !canImport"
						data-testid="sellos-import-run"
						@click="run"
					>
						Import {{ preview.counts.rows - preview.counts.skipped }} rows
					</AppButton>
				</div>
			</SectionCard>
		</div>

		<SectionCard
			v-if="result"
			title="Import done"
			data-testid="sellos-import-result"
			role="status"
		>
			<p class="ui-text-strong">
				{{ result.counts.new_leads }} leads imported, {{ result.merged.length }} merged
				into leads already there, {{ result.counts.skipped }} skipped.
			</p>
			<p class="mt-1 ui-text-muted">
				{{ result.counts.registered_dnd }} are registered on the do not call list. They can
				still be called, with the warning shown.
			</p>
			<ul v-if="result.skipped.length" class="mt-ui-sm ui-text-muted">
				<li v-for="s in result.skipped" :key="s.row">Row {{ s.row }}: {{ s.reason }}</li>
			</ul>
			<router-link
				class="ui-link mt-ui-md inline-flex min-h-touch items-center ui-text-strong"
				:to="{ path: '/crm/leads', query: { source: 'Bought list' } }"
				data-testid="sellos-import-view-leads"
			>
				See the imported leads
			</router-link>
		</SectionCard>
	</PageTemplate>
</template>

<script setup>
import { computed, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import FileField from "../components/FileField.vue";
import FieldGrid from "../components/FieldGrid.vue";
import FormField from "../components/FormField.vue";
import KpiStrip from "../components/KpiStrip.vue";
import SectionCard from "../components/SectionCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import Notice from "../components/Notice.vue";
import PageTemplate from "../components/PageTemplate.vue";
import { crmApi, serverMessage } from "../crm/crmApi";

// The Company Admin's bought list import (SOS-P1-12). The file is read in the browser and sent as text.
// The preview writes nothing; the import writes and the result is what the server says it did.
const csvText = ref("");
const listName = ref("");
const mapping = reactive({});
const preview = ref(null);
const result = ref(null);
const error = ref("");
const busy = ref(false);
const retry = () => (csvText.value ? load(cleanMapping()) : (error.value = ""));
const actions = {
	create: "New lead",
	"add lead": "New lead for a client already in SellOS",
	merge: "Merged into the existing lead",
};

const kpis = computed(() => {
	const c = preview.value?.counts;
	if (!c) return [];
	return [
		{ label: "Rows", value: c.rows, caption: "in the file", icon: "lucide-rows-3" },
		{
			label: "New leads",
			value: c.new_leads,
			caption: "will be made",
			icon: "lucide-user-plus",
			tone: "success",
		},
		{
			label: "Merged",
			value: c.merged_with_existing + c.merged_in_file,
			caption: "into one person each",
			icon: "lucide-merge",
			tone: "info",
		},
		{
			label: "Skipped",
			value: c.skipped,
			caption: "left out",
			icon: "lucide-circle-slash",
			tone: "warning",
		},
	];
});
const sampleColumns = [
	{ key: "rows", label: "Rows" },
	{ key: "name", label: "Name", primary: true },
	{ key: "phone", label: "Phone" },
	{ key: "email", label: "Email" },
	{ key: "action", label: "What happens", wrap: true },
	{ key: "do_not_call", label: "Do not call" },
];

const canImport = computed(
	() => preview.value && preview.value.counts.rows > preview.value.counts.skipped
);

const cleanMapping = () => Object.fromEntries(Object.entries(mapping).filter(([, v]) => v));

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

async function load(useMapping) {
	result.value = null;
	const data = await ask(
		() => crmApi.previewLeadImport(csvText.value, useMapping),
		"The file could not be read."
	);
	if (!data) {
		preview.value = null;
		return;
	}
	preview.value = data;
	for (const key of Object.keys(mapping)) delete mapping[key];
	for (const f of data.fields) mapping[f.field] = data.mapping[f.field] || "";
}

async function chooseFile(event) {
	const file = event.target.files?.[0];
	if (!file) return;
	csvText.value = await file.text();
	if (!listName.value) listName.value = file.name.replace(/\.[^.]+$/, "");
	await load(null);
}

const refresh = () => load(cleanMapping());

// A column is chosen from a frappe-ui select: the value goes in the mapping, then the preview is read again.
const mapColumn = (field, value) => {
	mapping[field] = value;
	refresh();
};
const columnOptions = computed(() => [
	{ label: "Not in the file", value: "" },
	...(preview.value?.headers || []).map((h) => ({ label: h, value: h })),
]);

async function run() {
	const data = await ask(
		() => crmApi.importBoughtList(csvText.value, cleanMapping(), listName.value),
		"The import failed."
	);
	if (data) {
		result.value = data;
		preview.value = null;
		csvText.value = "";
	}
}
</script>
