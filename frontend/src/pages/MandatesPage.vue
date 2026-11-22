<template>
	<div data-testid="sellos-mandates-page">
		<PageHeader
			title="Mandates"
			text="A mandate is the owner's signed agreement that we sell the property. The Private Sale Dossier is shared only once the mandate is signed, and every time it is opened is recorded."
			icon="lucide-file-signature"
		/>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-mandate-error"
			class="mb-ui-md text-sm text-accent"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-mandate-notice"
			class="mb-ui-md text-sm text-ink"
		>
			{{ notice }}
		</p>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-mandate-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<ListCard title="Mandates">
			<EmptyState
				v-if="loaded && !loadError && !mandates.length"
				title="No mandates yet"
				text="Record the first mandate below."
				icon="lucide-file-signature"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-mandate-list">
				<li
					v-for="m in mandates"
					:key="m.name"
					data-testid="sellos-mandate-row"
					:data-name="m.name"
					:data-title="m.lead_title"
					:data-status="m.status"
					class="rounded-input border border-line-soft p-ui-md"
				>
					<div class="flex flex-wrap items-center gap-3">
						<span class="font-medium text-ink" data-testid="sellos-mandate-title">{{
							m.lead_title
						}}</span>
						<StatusBadge
							:tone="m.status === 'Signed' ? 'success' : 'warning'"
							:label="m.status"
							data-testid="sellos-mandate-status"
						/>
						<span class="text-sm text-ink-muted" data-testid="sellos-mandate-terms">
							{{ m.mandate_type }}, {{ m.term_months }} months from
							{{ m.start_date }}, fee {{ m.fee_percent }}%
						</span>
					</div>

					<div v-if="m.status !== 'Signed'" class="mt-ui-sm">
						<p class="text-sm text-ink-muted">
							Upload the signed document to sign this mandate. It is required.
						</p>
						<FileField
							label="Signed document"
							accept=".pdf,.png,.jpg,.jpeg"
							required
							:hint="`A ${fileTypes} file of up to ${fileLimit} MB.`"
							data-testid="sellos-mandate-sign-file"
							@change="(e) => sign(m, e)"
						/>
					</div>
					<p
						v-else
						class="mt-ui-sm text-sm text-ink-muted"
						data-testid="sellos-mandate-signed"
					>
						Signed on {{ m.signed_on }} (recorded by {{ m.signed_by_name }}). Its terms
						are kept.
					</p>

					<div class="mt-ui-sm rounded-input bg-subtle p-ui-md">
						<h3 class="font-medium text-ink">Private Sale Dossier</h3>
						<p
							v-if="!m.dossier_released"
							class="mt-1 text-sm text-ink-muted"
							data-testid="sellos-mandate-dossier-locked"
						>
							The Dossier is hidden until the mandate is signed. Notes and files you
							add now are kept and released with the signature.
						</p>
						<div v-else class="mt-1">
							<AppButton
								type="button"
								data-testid="sellos-mandate-dossier-open"
								@click="open(m)"
							>
								Open the Dossier ({{ m.dossier_count }})
							</AppButton>
						</div>
						<div
							v-if="dossier[m.name]"
							class="mt-ui-sm space-y-ui-sm"
							data-testid="sellos-mandate-dossier"
						>
							<ul class="space-y-1">
								<li v-if="!dossier[m.name].items.length">The Dossier is empty.</li>
								<li
									v-for="(i, n) in dossier[m.name].items"
									:key="n"
									data-testid="sellos-mandate-dossier-item"
									:data-title="i.title"
									class="text-sm text-ink"
								>
									<span class="font-medium">{{ i.title }}</span>
									<span v-if="i.kind === 'Note'">: {{ i.note }}</span>
									<a
										v-else
										:href="i.file"
										target="_blank"
										rel="noopener"
										class="underline"
									>
										(file)
									</a>
									<span class="text-ink-muted">
										, added by {{ i.added_by_name }} on {{ i.added_on }}</span
									>
								</li>
							</ul>
							<p class="text-sm font-medium text-ink">Who has opened it</p>
							<ul
								class="space-y-1 text-sm text-ink-muted"
								data-testid="sellos-mandate-views"
							>
								<li
									v-for="(v, n) in dossier[m.name].views"
									:key="n"
									data-testid="sellos-mandate-view"
								>
									{{ v.viewed_by_name }}, {{ v.viewed_on }}
								</li>
							</ul>
						</div>
						<div class="mt-ui-sm grid gap-ui-sm md:grid-cols-2">
							<FormField
								v-model="noteTitle[m.name]"
								label="Note title"
								data-testid="sellos-mandate-note-title"
							/>
							<FormField
								v-model="noteText[m.name]"
								type="textarea"
								label="Note"
								data-testid="sellos-mandate-note-text"
							/>
						</div>
						<div class="mt-ui-sm flex flex-wrap items-end gap-ui-sm">
							<AppButton
								type="button"
								data-testid="sellos-mandate-note-add"
								@click="addNote(m)"
							>
								Add note
							</AppButton>
							<FileField
								label="Add a file to the Dossier"
								accept=".pdf,.png,.jpg,.jpeg"
								data-testid="sellos-mandate-dossier-file"
								@change="(e) => addFile(m, e)"
							/>
						</div>
					</div>
				</li>
			</ul>
		</ListCard>

		<ListCard title="Record a mandate" class="mt-ui-lg">
			<div class="grid gap-ui-md md:grid-cols-2">
				<FormField
					v-model="form.lead"
					type="select"
					label="Seller"
					:options="sellerOptions"
					required
					data-testid="sellos-mandate-lead"
				/>
				<FormField
					v-model="form.mandate_type"
					type="select"
					label="Type"
					:options="typeOptions"
					required
					data-testid="sellos-mandate-type"
				/>
				<FormField
					v-model="form.term_months"
					type="number"
					label="Term (months)"
					required
					data-testid="sellos-mandate-term"
				/>
				<FormField
					v-model="form.fee_percent"
					type="number"
					label="Fee (% of the sale price)"
					required
					data-testid="sellos-mandate-fee"
				/>
			</div>
			<div class="mt-ui-md">
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-mandate-save"
					@click="save"
				>
					Record mandate
				</AppButton>
			</div>
		</ListCard>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import FileField from "../components/FileField.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { readFileBase64 } from "../company/partnersApi";
import { serverMessage } from "../crm/crmApi";
import { mandateApi } from "../crm/mandatesApi";

// Mandates (SOS-P4-05). Every change is made on the server and the list read back, so what is shown is what is
// saved. The server decides whether the Dossier is released: until the mandate is signed it sends no item of it.
const mandates = ref([]);
const sellers = ref([]);
const types = ref([]);
const fileTypes = ref("PDF, PNG or JPG");
const fileLimit = ref(5);
const dossier = reactive({});
const noteTitle = reactive({});
const noteText = reactive({});
const form = reactive({ lead: "", mandate_type: "Exclusive", term_months: "", fee_percent: "" });
const error = ref("");
const notice = ref("");
const loadError = ref("");
const loaded = ref(false);

const sellerOptions = computed(() => [
	{ label: "Choose a seller", value: "" },
	...sellers.value.map((s) => ({ label: s.label, value: s.value })),
]);
const typeOptions = computed(() => types.value.map((t) => ({ label: t, value: t })));

async function load() {
	loadError.value = "";
	try {
		const result = await mandateApi.overview();
		mandates.value = result.mandates;
		sellers.value = result.sellers;
		types.value = result.mandate_types;
		fileTypes.value = result.file_types;
		fileLimit.value = result.file_limit_mb;
	} catch (e) {
		loadError.value = serverMessage(e, "The mandates could not be loaded.");
	} finally {
		loaded.value = true;
	}
}

async function run(action, done, failed) {
	error.value = "";
	notice.value = "";
	try {
		await action();
		notice.value = done;
		await load();
	} catch (e) {
		error.value = serverMessage(e, failed);
	}
}

const save = () => {
	if (!form.lead || !form.term_months || !form.fee_percent) {
		error.value = "Choose a seller and enter the term and the fee.";
		return Promise.resolve();
	}
	return run(
		async () => {
			await mandateApi.save({ ...form });
			form.lead = "";
			form.term_months = "";
			form.fee_percent = "";
		},
		"The mandate is recorded as a draft. Upload the signed document to sign it.",
		"The mandate could not be recorded."
	);
};

async function chosen(event) {
	const file = event.target.files?.[0];
	if (!file) return null;
	const content = await readFileBase64(file);
	event.target.value = "";
	return { name: file.name, content };
}

async function sign(m, event) {
	const file = await chosen(event);
	if (!file) return;
	await run(
		() => mandateApi.sign(m.name, file.name, file.content),
		`${m.lead_title}: the mandate is signed and its Dossier is released.`,
		"The mandate could not be signed."
	);
}

async function addNote(m) {
	await run(
		async () => {
			await mandateApi.addNote(m.name, noteTitle[m.name] || "", noteText[m.name] || "");
			noteTitle[m.name] = "";
			noteText[m.name] = "";
		},
		"The note is added to the Dossier.",
		"The note could not be added."
	);
}

async function addFile(m, event) {
	const file = await chosen(event);
	if (!file) return;
	await run(
		() => mandateApi.addFile(m.name, "", file.name, file.content),
		"The file is added to the Dossier.",
		"The file could not be added."
	);
}

async function open(m) {
	error.value = "";
	notice.value = "";
	try {
		dossier[m.name] = await mandateApi.openDossier(m.name);
	} catch (e) {
		error.value = serverMessage(e, "The Dossier could not be opened.");
	}
}

onMounted(load);
</script>
