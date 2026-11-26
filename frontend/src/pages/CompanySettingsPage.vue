<template>
	<PageTemplate shape="form" data-testid="sellos-settings-page">
		<template #header>
			<PageHeader
				title="Company settings"
				text="The note types your team uses, and the connections your company has set up."
				icon="lucide-settings"
			/>
		</template>

		<p v-if="notice" role="status" class="ui-text-small" data-testid="sellos-settings-notice">
			{{ notice }}
		</p>
		<p v-if="error" role="alert" class="ui-text-error" data-testid="sellos-settings-error">
			{{ error }}
		</p>

		<SectionCard
			title="Note types"
			help="Every note has a type. Rename a type, add your own or hide one you do not use. A hidden type is not offered for new notes, and old notes keep it."
			data-testid="sellos-note-types"
		>
			<template #actions>
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-note-type-new"
					@click="openAdd"
				>
					Add type
				</AppButton>
			</template>
			<DataTable
				caption="Note types"
				dense
				:columns="columns"
				:rows="types"
				:actions="actions"
				:row-name="(row) => row.label"
				:row-attrs="(row) => ({ 'data-label': row.label })"
				:loading="!loaded"
				empty-title="No types"
				testid="sellos-note-type-list"
				row-testid="sellos-note-type-row"
			>
				<template #cell-enabled="{ row }">
					<StatusBadge
						:tone="row.enabled ? 'success' : 'neutral'"
						:label="row.enabled ? 'Shown' : 'Hidden'"
					/>
				</template>
			</DataTable>
		</SectionCard>

		<FormDrawer
			:open="drawer"
			:title="editing ? 'Rename note type' : 'Add a note type'"
			text="Up to 40 characters."
			submit-label="Save"
			testid="sellos-note-type-form"
			submit-testid="sellos-note-type-save"
			@close="drawer = false"
			@submit="save"
		>
			<FormSection title="Type">
				<FormField
					v-model="label"
					label="Name"
					required
					data-testid="sellos-note-type-name"
				/>
			</FormSection>
			<p v-if="error" role="alert" class="ui-text-error">{{ error }}</p>
		</FormDrawer>
	</PageTemplate>
</template>

<script setup>
import { onMounted, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import SectionCard from "../components/SectionCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { notesApi } from "../crm/notesApi";

// Company settings (SOS-LOOP): the managed list of note types, and the DocuSeal connection. A Company Admin only.
const types = ref([]);
const loaded = ref(false);
const error = ref("");
const notice = ref("");
const drawer = ref(false);
const editing = ref("");
const label = ref("");
const editingEnabled = ref(1);

const columns = [
	{ key: "label", label: "Name", primary: true, sortable: true },
	{ key: "enabled", label: "Status", sortable: true },
];
const actions = (row) => [
	{ label: "Rename", icon: "lucide-pencil", onClick: () => openRename(row) },
	...(row.is_other
		? []
		: [
				{
					label: row.enabled ? "Hide" : "Show",
					icon: row.enabled ? "lucide-eye-off" : "lucide-eye",
					onClick: () => toggle(row),
				},
		  ]),
];

async function load() {
	try {
		types.value = (await notesApi.typeSettings()).types;
	} catch (e) {
		error.value = serverMessage(e, "The note types could not be loaded.");
	} finally {
		loaded.value = true;
	}
}
function openAdd() {
	editing.value = "";
	label.value = "";
	error.value = "";
	drawer.value = true;
}
function openRename(row) {
	editing.value = row.name;
	editingEnabled.value = row.enabled;
	label.value = row.label;
	error.value = "";
	drawer.value = true;
}
async function run(action, done) {
	error.value = "";
	notice.value = "";
	try {
		types.value = (await action()).types;
		notice.value = done;
		drawer.value = false;
	} catch (e) {
		error.value = serverMessage(e, "The note type could not be saved.");
	}
}
const save = () =>
	run(
		() =>
			notesApi.saveType(
				label.value,
				editing.value || null,
				editing.value ? editingEnabled.value : 1
			),
		editing.value ? "The type is renamed." : "The type is added."
	);
const toggle = (row) =>
	run(
		() => notesApi.saveType(row.label, row.name, row.enabled ? 0 : 1),
		row.enabled ? `${row.label} is hidden.` : `${row.label} is shown again.`
	);

onMounted(load);
</script>
