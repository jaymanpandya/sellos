<template>
	<PageTemplate shape="record" data-testid="sellos-mandate-page">
		<template #header>
			<RecordHeader
				:title="mandate ? mandate.lead_title : 'Mandate'"
				:line="line"
				back-to="/crm/mandates"
				back-label="Back to mandates"
				title-testid="sellos-mandate-title"
			>
				<template v-if="mandate" #status>
					<StatusBadge
						:tone="mandate.status === 'Signed' ? 'success' : 'warning'"
						:label="mandate.status"
						data-testid="sellos-mandate-status"
					/>
					<SigningBadge :status="mandate.signing_status" />
				</template>
				<template v-if="mandate" #actions>
					<AppButton
						type="button"
						data-testid="sellos-mandate-seller-link"
						@click="router.push(`/crm/sellers/${mandate.lead}`)"
					>
						Open the seller
					</AppButton>
				</template>
			</RecordHeader>
		</template>

		<template v-if="mandate" #tabs>
			<PageTabs v-model="tab" :tabs="tabs" label="Mandate sections" />
		</template>

		<LoadError
			v-if="loadError"
			:message="loadError"
			data-testid="sellos-mandate-load-error"
			@retry="load"
		/>
		<LoadingSkeleton v-else-if="!loaded" :rows="4" label="Loading the mandate." />
		<EmptyState
			v-else-if="!mandate"
			title="This mandate was not found"
			text="It may be archived, or you may not be allowed to see it."
			icon="lucide-file-signature"
		/>

		<template v-if="mandate">
			<p v-if="error" role="alert" data-testid="sellos-mandate-error" class="ui-text-error">
				{{ error }}
			</p>
			<p
				v-if="notice"
				role="status"
				data-testid="sellos-mandate-notice"
				class="ui-text-small"
			>
				{{ notice }}
			</p>

			<div v-if="tab === 'notes'" id="panel-notes" role="tabpanel" class="space-y-4">
				<NotesPanel :mandate="mandate.name" />
			</div>

			<div v-if="tab === 'overview'" id="panel-overview" role="tabpanel" class="space-y-4">
				<SectionCard title="Terms">
					<dl>
						<FieldGrid>
							<ReadField label="Type" :value="mandate.mandate_type" />
							<ReadField
								label="Term"
								:value="mandate.term_months ? `${mandate.term_months} months` : ''"
							/>
							<ReadField label="Starts" :value="formatDate(mandate.start_date)" />
							<ReadField label="Ends" :value="formatDate(mandate.ends_on)" />
							<ReadField
								label="Fee"
								:value="
									mandate.fee_percent
										? `${mandate.fee_percent}% of the sale price`
										: ''
								"
							/>
						</FieldGrid>
					</dl>
				</SectionCard>

				<SectionCard
					title="Electronic signing"
					help="DocuSeal emails the seller and your signer. This is an electronic signature, not an Aadhaar eSign."
				>
					<MandateSigning :mandate="mandate" @changed="changed" />
				</SectionCard>

				<SectionCard title="Signature">
					<div v-if="mandate.status !== 'Signed'">
						<p class="mb-ui-sm ui-text-muted">
							Or upload a signed document yourself to sign this mandate. It is
							required.
						</p>
						<FileField
							label="Signed document"
							accept=".pdf,.png,.jpg,.jpeg"
							required
							:hint="`A ${fileTypes} file of up to ${fileLimit} MB.`"
							data-testid="sellos-mandate-sign-file"
							@change="sign"
						/>
					</div>
					<template v-else>
						<p class="ui-text-muted" data-testid="sellos-mandate-signed">
							Signed on {{ formatWhen(mandate.signed_on) }} (recorded by
							{{ mandate.signed_by_name }}). Its terms are kept.
						</p>
						<a
							v-if="mandate.signed_document"
							:href="mandate.signed_document"
							target="_blank"
							rel="noopener"
							class="ui-link"
							data-testid="sellos-mandate-signed-copy"
							>Download signed copy</a
						>
					</template>
				</SectionCard>
			</div>

			<div v-if="tab === 'dossier'" id="panel-dossier" role="tabpanel" class="space-y-4">
				<SectionCard title="Private Sale Dossier">
					<p
						v-if="!mandate.dossier_released"
						class="ui-text-muted"
						data-testid="sellos-mandate-dossier-locked"
					>
						The Dossier is hidden until the mandate is signed. Notes and files you add
						now are kept and released with the signature.
					</p>
					<div v-else>
						<AppButton
							type="button"
							data-testid="sellos-mandate-dossier-open"
							@click="open"
						>
							Open the Dossier ({{ mandate.dossier_count }})
						</AppButton>
					</div>
					<div
						v-if="dossier"
						class="mt-ui-sm space-y-ui-sm"
						data-testid="sellos-mandate-dossier"
					>
						<ul class="space-y-1">
							<li v-if="!dossier.items.length">The Dossier is empty.</li>
							<li
								v-for="(i, n) in dossier.items"
								:key="n"
								data-testid="sellos-mandate-dossier-item"
								:data-title="i.title"
								class="ui-text-small"
							>
								<span class="ui-text-strong">{{ i.title }}</span>
								<span v-if="i.kind === 'Note'">: {{ i.note }}</span>
								<a
									v-else
									:href="i.file"
									target="_blank"
									rel="noopener"
									class="ui-link"
								>
									(file)
								</a>
								<span class="ui-text-muted">
									, added by {{ i.added_by_name }} on
									{{ formatWhen(i.added_on) }}</span
								>
							</li>
						</ul>
						<p class="ui-text-strong">Who has opened it</p>
						<ul class="space-y-1 ui-text-muted" data-testid="sellos-mandate-views">
							<li
								v-for="(v, n) in dossier.views"
								:key="n"
								data-testid="sellos-mandate-view"
							>
								{{ v.viewed_by_name }}, {{ formatWhen(v.viewed_on) }}
							</li>
						</ul>
					</div>
				</SectionCard>

				<SectionCard v-if="mandate.dossier_released" title="Dossier PDF">
					<DossierPdf :mandate="mandate" :pdf="mandate.dossier_pdf" @changed="changed" />
				</SectionCard>

				<SectionCard title="Add to the Dossier">
					<div class="grid gap-ui-sm">
						<FormField
							v-model="noteTitle"
							label="Note title"
							data-testid="sellos-mandate-note-title"
						/>
						<FormField
							v-model="noteText"
							type="textarea"
							label="Note"
							data-testid="sellos-mandate-note-text"
						/>
						<div class="flex flex-wrap items-end gap-ui-sm">
							<AppButton
								type="button"
								data-testid="sellos-mandate-note-add"
								@click="addNote"
							>
								Add note
							</AppButton>
							<FileField
								label="Add a file to the Dossier"
								accept=".pdf,.png,.jpg,.jpeg"
								data-testid="sellos-mandate-dossier-file"
								@change="addFile"
							/>
						</div>
					</div>
				</SectionCard>
			</div>
		</template>

		<template #side>
			<SectionCard title="Summary">
				<dl v-if="mandate">
					<FieldGrid :columns="1">
						<ReadField label="Seller" :value="mandate.lead_title" />
						<ReadField label="Client" :value="mandate.client_name" />
						<ReadField label="Status" :value="mandate.status" />
						<ReadField
							label="Fee"
							:value="mandate.fee_percent ? `${mandate.fee_percent}%` : ''"
						/>
					</FieldGrid>
				</dl>
				<p v-else class="ui-text-muted">The mandate is loading.</p>
			</SectionCard>
			<SectionCard title="History">
				<ul v-if="mandate" class="space-y-1 ui-text-muted">
					<li v-if="mandate.status === 'Signed'">
						Signed on {{ formatWhen(mandate.signed_on) }} by
						{{ mandate.signed_by_name }}.
					</li>
					<li v-else>Drafted, waiting for the signed document.</li>
					<li v-if="mandate.dossier_released">
						The Dossier is released ({{ mandate.dossier_count }} items).
					</li>
					<li v-else>The Dossier is hidden until the signature.</li>
				</ul>
				<p v-else class="ui-text-muted">No history yet.</p>
			</SectionCard>
		</template>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import FieldGrid from "../components/FieldGrid.vue";
import FileField from "../components/FileField.vue";
import FormField from "../components/FormField.vue";
import DossierPdf from "../components/DossierPdf.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import MandateSigning from "../components/MandateSigning.vue";
import NotesPanel from "../components/NotesPanel.vue";
import PageTabs from "../components/PageTabs.vue";
import PageTemplate from "../components/PageTemplate.vue";
import ReadField from "../components/ReadField.vue";
import RecordHeader from "../components/RecordHeader.vue";
import SectionCard from "../components/SectionCard.vue";
import SigningBadge from "../components/SigningBadge.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { readFileBase64 } from "../company/partnersApi";
import { serverMessage } from "../crm/crmApi";
import { mandateApi } from "../crm/mandatesApi";
import { formatDate, formatWhen } from "../format";

// One mandate (SOS-P4-05). There is no call that returns a single mandate, so the page loads the list the Mandates
// page loads and picks its record by name. The server decides whether the Dossier is released: until the mandate
// is signed it sends no item of it.
const route = useRoute();
const router = useRouter();
const mandate = ref(null);
const fileTypes = ref("PDF, PNG or JPG");
const fileLimit = ref(5);
const dossier = ref(null);
const noteTitle = ref("");
const noteText = ref("");
const tab = ref("overview");
const error = ref("");
const notice = ref("");
const loadError = ref("");
const loaded = ref(false);

const tabs = computed(() => [
	{ key: "overview", label: "Overview" },
	{ key: "dossier", label: "Dossier" },
	{ key: "notes", label: "Notes" },
]);
const line = computed(() =>
	mandate.value
		? [mandate.value.client_name, mandate.value.mandate_type].filter(Boolean).join(", ")
		: ""
);

async function load() {
	loadError.value = "";
	try {
		const result = await mandateApi.overview();
		mandate.value = result.mandates.find((m) => m.name === route.params.name) || null;
		fileTypes.value = result.file_types;
		fileLimit.value = result.file_limit_mb;
	} catch (e) {
		loadError.value = serverMessage(e, "The mandate could not be loaded.");
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

async function changed(message) {
	notice.value = message;
	await load();
}

async function chosen(event) {
	const file = event.target.files?.[0];
	if (!file) return null;
	const content = await readFileBase64(file);
	event.target.value = "";
	return { name: file.name, content };
}

async function sign(event) {
	const file = await chosen(event);
	if (!file) return;
	await run(
		() => mandateApi.sign(mandate.value.name, file.name, file.content),
		`${mandate.value.lead_title}: the mandate is signed and its Dossier is released.`,
		"The mandate could not be signed."
	);
}

async function addNote() {
	await run(
		async () => {
			await mandateApi.addNote(
				mandate.value.name,
				noteTitle.value || "",
				noteText.value || ""
			);
			noteTitle.value = "";
			noteText.value = "";
		},
		"The note is added to the Dossier.",
		"The note could not be added."
	);
}

async function addFile(event) {
	const file = await chosen(event);
	if (!file) return;
	await run(
		() => mandateApi.addFile(mandate.value.name, "", file.name, file.content),
		"The file is added to the Dossier.",
		"The file could not be added."
	);
}

async function open() {
	error.value = "";
	notice.value = "";
	try {
		dossier.value = await mandateApi.openDossier(mandate.value.name);
	} catch (e) {
		error.value = serverMessage(e, "The Dossier could not be opened.");
	}
}

onMounted(load);
</script>
