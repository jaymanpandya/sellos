<template>
	<SectionCard
		title="Notes"
		help="Call notes, site visits, price talks and papers."
		:data-testid="testid"
	>
		<template #actions>
			<AppButton
				type="button"
				variant="primary"
				data-testid="sellos-note-new"
				@click="openNew"
			>
				<template #prefix
					><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
				/></template>
				Add note
			</AppButton>
		</template>

		<div class="mb-4 max-w-xs">
			<FormField
				v-model="filter"
				compact
				type="select"
				label="Type"
				:options="filterOptions"
				data-testid="sellos-note-filter"
			/>
		</div>

		<p
			v-if="error && !open"
			role="alert"
			class="mb-3 ui-text-error"
			data-testid="sellos-note-error"
		>
			{{ error }}
		</p>
		<LoadingSkeleton v-if="!loaded" :rows="2" label="Loading the notes." />
		<EmptyState
			v-else-if="!shown.length"
			:title="filter ? 'No note of this type' : 'No notes yet'"
			text="Add the first note."
			icon="lucide-notebook-pen"
			data-testid="sellos-note-empty"
		/>
		<ol v-else class="ml-1 space-y-5 border-l border-line pl-5" data-testid="sellos-note-list">
			<li
				v-for="note in shown"
				:key="note.name"
				class="relative"
				data-testid="sellos-note"
				:data-type="note.type_label"
			>
				<span
					class="absolute -left-[1.65rem] top-1.5 size-2 rounded-round bg-brand"
					aria-hidden="true"
				/>
				<div class="flex flex-wrap items-center gap-2">
					<StatusBadge
						:label="note.type_label"
						tone="info"
						data-testid="sellos-note-type"
					/>
					<span class="ui-text-strong">{{ note.author_name }}</span>
					<span class="ui-text-muted">{{ formatWhen(note.created) }}</span>
					<span v-if="note.edited" class="ui-text-muted">edited</span>
					<span v-if="note.mandate" class="ui-text-muted">on the mandate</span>
				</div>
				<p
					v-if="note.body"
					class="mt-1 whitespace-pre-line ui-text-body"
					data-testid="sellos-note-body"
				>
					{{ note.body }}
				</p>
				<div v-if="note.attachments.length" class="mt-2 flex flex-wrap items-start gap-3">
					<a
						v-for="a in note.attachments.filter((x) => x.kind === 'Image')"
						:key="a.file"
						:href="a.file"
						target="_blank"
						rel="noopener"
						data-testid="sellos-note-image"
					>
						<img
							:src="a.file"
							:alt="a.file_name"
							class="h-20 w-20 rounded-control border border-line object-cover"
							loading="lazy"
						/>
					</a>
					<ul class="space-y-1">
						<li
							v-for="a in note.attachments.filter((x) => x.kind !== 'Image')"
							:key="a.file"
						>
							<a
								:href="a.file"
								target="_blank"
								rel="noopener"
								class="ui-link"
								data-testid="sellos-note-document"
								>{{ a.file_name }}</a
							>
							<span class="ui-text-muted"> ({{ formatSize(a.size) }})</span>
						</li>
					</ul>
				</div>
				<div v-if="note.can_edit" class="mt-2 flex gap-2">
					<AppButton
						type="button"
						data-testid="sellos-note-edit"
						@click="openEdit(note)"
					>
						Edit
					</AppButton>
					<AppButton
						v-if="confirming !== note.name"
						type="button"
						data-testid="sellos-note-remove"
						@click="confirming = note.name"
					>
						Remove
					</AppButton>
					<AppButton
						v-else
						type="button"
						variant="danger"
						data-testid="sellos-note-remove-confirm"
						@click="remove(note)"
					>
						Remove this note
					</AppButton>
				</div>
			</li>
		</ol>

		<FormDrawer
			:open="open"
			:title="editing ? 'Edit note' : 'Add note'"
			text="Choose the type, write what happened and attach photos or papers."
			submit-label="Save note"
			testid="sellos-note-form"
			submit-testid="sellos-note-save"
			@close="close"
			@submit="save"
		>
			<FormSection title="Note">
				<FormField
					v-model="form.note_type"
					type="select"
					label="Type"
					:options="typeOptions"
					required
					data-testid="sellos-note-type-select"
				/>
				<FormField
					v-if="isOther"
					v-model="form.custom_label"
					label="Short label"
					required
					hint="Up to 40 characters."
					data-testid="sellos-note-label"
				/>
				<FormField
					v-model="form.body"
					type="textarea"
					label="Note"
					data-testid="sellos-note-text"
				/>
				<FileField
					label="Attachments"
					multiple
					accept=".png,.jpg,.jpeg,.webp,.pdf,.docx,.xlsx,.txt,.csv"
					hint="Photos, PDF, DOCX, XLSX, TXT or CSV. Up to 5 files of 10 MB each."
					data-testid="sellos-note-files"
					@change="pick"
				/>
				<p
					v-for="f in form.files"
					:key="f.filename"
					class="ui-text-small"
					data-testid="sellos-note-picked"
				>
					{{ f.filename }}
				</p>
			</FormSection>
			<p v-if="error" role="alert" class="ui-text-error" data-testid="sellos-note-error">
				{{ error }}
			</p>
		</FormDrawer>
	</SectionCard>
</template>

<script setup>
// The notes of a lead, a seller or a mandate (SOS-LOOP): a timeline with the type as a pill, a filter by type, a
// drawer to add or edit one with attachments, and thumbnails for images. Everything is done on the server, which
// judges each call on the record. Give `lead`, or `mandate` for a mandate's own notes.
import { computed, onMounted, reactive, ref, watch } from "vue";

import AppButton from "./AppButton.vue";
import EmptyState from "./EmptyState.vue";
import FileField from "./FileField.vue";
import FormDrawer from "./FormDrawer.vue";
import FormField from "./FormField.vue";
import FormSection from "./FormSection.vue";
import LoadingSkeleton from "./LoadingSkeleton.vue";
import SectionCard from "./SectionCard.vue";
import StatusBadge from "./StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { notesApi } from "../crm/notesApi";
import { formatWhen } from "../format";

const props = defineProps({
	lead: { type: String, default: "" },
	mandate: { type: String, default: "" },
	testid: { type: String, default: "sellos-notes" },
});

const notes = ref([]);
const types = ref([]);
const loaded = ref(false);
const error = ref("");
const filter = ref("");
const open = ref(false);
const editing = ref("");
const confirming = ref("");
const blank = () => ({ note_type: "", custom_label: "", body: "", files: [] });
const form = reactive(blank());

const target = () => (props.mandate ? { mandate: props.mandate } : { lead: props.lead });
const filterOptions = computed(() => [
	{ label: "All types", value: "" },
	...types.value.map((t) => ({ label: t.label, value: t.name })),
]);
const typeOptions = computed(() => [
	{ label: "Choose a type", value: "" },
	...types.value.map((t) => ({ label: t.label, value: t.name })),
]);
const isOther = computed(() => types.value.find((t) => t.name === form.note_type)?.is_other);
const shown = computed(() =>
	filter.value ? notes.value.filter((n) => n.note_type === filter.value) : notes.value
);

function formatSize(bytes) {
	return bytes >= 1048576
		? `${(bytes / 1048576).toFixed(1)} MB`
		: `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

async function load() {
	try {
		const result = await notesApi.list(target());
		notes.value = result.notes;
		types.value = result.types;
	} catch (e) {
		error.value = serverMessage(e, "The notes could not be loaded.");
	} finally {
		loaded.value = true;
	}
}

function openNew() {
	Object.assign(form, blank());
	editing.value = "";
	error.value = "";
	open.value = true;
}
function openEdit(note) {
	Object.assign(form, {
		note_type: note.note_type,
		custom_label: note.custom_label,
		body: note.body,
		files: [],
	});
	editing.value = note.name;
	error.value = "";
	open.value = true;
}
function close() {
	open.value = false;
	error.value = "";
}

function read(file) {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () =>
			resolve({ filename: file.name, content_base64: String(reader.result).split(",")[1] });
		reader.onerror = reject;
		reader.readAsDataURL(file);
	});
}
async function pick(event) {
	form.files = await Promise.all([...event.target.files].map(read));
}

async function save() {
	error.value = "";
	try {
		const params = {
			note_type: form.note_type,
			body: form.body,
			custom_label: form.custom_label,
			files: form.files,
		};
		const result = editing.value
			? await notesApi.update({ name: editing.value, ...params })
			: await notesApi.add({ ...target(), ...params });
		notes.value = result.notes;
		open.value = false;
	} catch (e) {
		error.value = serverMessage(e, "The note could not be saved.");
	}
}

async function remove(note) {
	error.value = "";
	try {
		notes.value = (await notesApi.remove(note.name)).notes;
		confirming.value = "";
	} catch (e) {
		error.value = serverMessage(e, "The note could not be removed.");
	}
}

watch(() => [props.lead, props.mandate], load);
onMounted(load);
</script>
