<template>
	<div class="max-w-3xl" data-testid="sellos-import-page">
		<h1 class="text-2xl font-semibold text-ink">Import a bought lead list</h1>
		<p class="mt-2 text-ink-muted">
			Choose a CSV file. Every lead comes in from the source Bought list with the consent
			status Unknown, or Registered DND when the file says the number is on the do not call
			list. A person already in SellOS, or twice in the file, is merged into one. Nothing
			here stops a call or a message: the warning shows on the lead.
		</p>
		<p v-if="error" role="alert" data-testid="sellos-import-error" class="mt-3 text-accent">
			{{ error }}
		</p>

		<section class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4">
			<label class="block text-sm text-ink-muted">
				CSV file
				<input
					type="file"
					accept=".csv,text/csv,text/plain"
					aria-label="CSV file"
					data-testid="sellos-import-file"
					class="field mt-1"
					@change="chooseFile"
				/>
			</label>
			<label class="block text-sm text-ink-muted">
				Name of the list
				<input
					v-model="listName"
					placeholder="For example Magicbricks Pune, November"
					data-testid="sellos-import-list-name"
					class="field mt-1"
				/>
			</label>
		</section>

		<section
			v-if="preview"
			class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4"
			data-testid="sellos-import-preview"
		>
			<h2 class="font-medium text-ink">Which column is which</h2>
			<div class="grid gap-2 sm:grid-cols-2">
				<label
					v-for="f in preview.fields"
					:key="f.field"
					class="block text-sm text-ink-muted"
				>
					{{ f.label }}
					<select
						v-model="mapping[f.field]"
						:aria-label="f.label"
						:data-testid="`sellos-import-map-${f.field}`"
						class="field mt-1"
						@change="refresh"
					>
						<option value="">Not in the file</option>
						<option v-for="h in preview.headers" :key="h" :value="h">{{ h }}</option>
					</select>
				</label>
			</div>

			<p class="text-sm text-ink" data-testid="sellos-import-counts">
				{{ preview.counts.rows }} rows: {{ preview.counts.new_leads }} new leads,
				{{ preview.counts.merged_with_existing }} merged with people already in SellOS,
				{{ preview.counts.merged_in_file }} merged within the file,
				{{ preview.counts.registered_dnd }} on the do not call list,
				{{ preview.counts.skipped }} skipped.
			</p>
			<p v-if="preview.counts.unrecognised_dnd" class="text-sm text-ink-muted">
				{{ preview.counts.unrecognised_dnd }} do not call values were not recognised and
				are treated as no result.
			</p>
			<table class="w-full text-sm" data-testid="sellos-import-sample">
				<thead>
					<tr class="text-left text-ink-muted">
						<th>Rows</th>
						<th>Name</th>
						<th>Phone</th>
						<th>Email</th>
						<th>What happens</th>
						<th>Do not call</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="r in preview.sample"
						:key="r.rows"
						data-testid="sellos-import-sample-row"
					>
						<td>{{ r.rows }}</td>
						<td>{{ r.name }}</td>
						<td>{{ r.phone }}</td>
						<td>{{ r.email }}</td>
						<td>{{ actions[r.action] }}</td>
						<td>{{ r.do_not_call }}</td>
					</tr>
				</tbody>
			</table>
			<ul
				v-if="preview.skipped.length"
				class="text-sm text-ink-muted"
				data-testid="sellos-import-skipped"
			>
				<li v-for="s in preview.skipped" :key="s.row">Row {{ s.row }}: {{ s.reason }}</li>
			</ul>
			<button
				type="button"
				class="btn"
				:disabled="busy || !canImport"
				data-testid="sellos-import-run"
				@click="run"
			>
				Import {{ preview.counts.rows - preview.counts.skipped }} rows
			</button>
		</section>

		<section
			v-if="result"
			class="mt-4 rounded-input border border-line bg-surface p-4"
			data-testid="sellos-import-result"
			role="status"
		>
			<p class="font-medium text-ink">
				{{ result.counts.new_leads }} leads imported, {{ result.merged.length }} merged
				into leads already there, {{ result.counts.skipped }} skipped.
			</p>
			<p class="mt-1 text-sm text-ink-muted">
				{{ result.counts.registered_dnd }} are registered on the do not call list. They can
				still be called, with the warning shown.
			</p>
			<ul v-if="result.skipped.length" class="mt-2 text-sm text-ink-muted">
				<li v-for="s in result.skipped" :key="s.row">Row {{ s.row }}: {{ s.reason }}</li>
			</ul>
			<router-link
				class="btn mt-3 inline-block"
				:to="{ path: '/crm/leads', query: { source: 'Bought list' } }"
				data-testid="sellos-import-view-leads"
			>
				See the imported leads
			</router-link>
		</section>
	</div>
</template>

<script setup>
import { computed, reactive, ref } from "vue";

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
const actions = {
	create: "New lead",
	"add lead": "New lead for a client already in SellOS",
	merge: "Merged into the existing lead",
};

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
