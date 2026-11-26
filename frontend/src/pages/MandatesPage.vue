<template>
	<PageTemplate data-testid="sellos-mandates-page">
		<template #header>
			<PageHeader
				title="Mandates"
				text="The owner's signed agreement that we sell the property. Its Private Sale Dossier opens only once it is signed."
				icon="lucide-file-signature"
			>
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-mandate-new"
					@click="openForm"
				>
					<template #prefix
						><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
					/></template>
					Record mandate
				</AppButton>
			</PageHeader>
		</template>

		<template v-if="!loadError" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-mandate-stats" />
		</template>

		<template v-if="!loadError" #filters>
			<FilterBar
				v-model:search="search"
				search-label="Search mandates"
				search-placeholder="Search by seller"
				search-testid="sellos-mandate-search"
				clear-testid="sellos-mandate-filter-clear"
				:active="Boolean(search || statusFilter || signingFilter || typeFilter)"
				:chips="chips"
				data-testid="sellos-mandate-filters"
				@clear="clearFilters"
				@remove-chip="removeChip"
			>
				<FormField
					v-model="statusFilter"
					compact
					type="select"
					label="Status"
					:options="statusOptions"
					data-testid="sellos-mandate-filter-status"
				/>
				<FormField
					v-model="signingFilter"
					compact
					type="select"
					label="Signing"
					:options="signingOptions"
					data-testid="sellos-mandate-filter-signing"
				/>
				<FormField
					v-model="typeFilter"
					compact
					type="select"
					label="Type"
					:options="typeFilterOptions"
					data-testid="sellos-mandate-filter-type"
				/>
			</FilterBar>
		</template>

		<p
			v-if="error && !creating && !current"
			role="alert"
			data-testid="sellos-mandate-error"
			class="mb-ui-md ui-text-error"
		>
			{{ error }}
		</p>
		<p
			v-if="notice && !current"
			role="status"
			data-testid="sellos-mandate-notice"
			class="mb-ui-md ui-text-small"
		>
			{{ notice }}
		</p>
		<LoadError
			v-if="loadError"
			:message="loadError"
			class="mb-ui-md"
			data-testid="sellos-mandate-load-error"
			@retry="load"
		/>

		<p
			v-if="bulkNotice"
			role="status"
			class="mb-ui-md ui-text-small"
			data-testid="sellos-mandate-bulk-result"
		>
			{{ bulkNotice }}
		</p>
		<!-- The bulk bar exists only while rows are selected. -->
		<BulkBar v-if="isAdmin" :count="selected.length" @clear="selected = []">
			<AppButton
				type="button"
				:disabled="!selected.length"
				data-testid="sellos-mandate-bulk-archive"
				@click="bulkArchive"
			>
				Archive selected mandates
			</AppButton>
		</BulkBar>

		<DataTable
			v-if="!loadError"
			v-model:selected="selected"
			:selectable="isAdmin"
			:actions="rowActions"
			select-testid="sellos-mandate-select"
			select-all-testid="sellos-mandate-select-all"
			title="All mandates"
			caption="Mandates"
			:columns="columns"
			:rows="shownMandates"
			:row-to="(row) => `/crm/mandates/${row.name}`"
			:loading="!loaded"
			loading-label="Loading mandates."
			:row-name="(row) => row.lead_title"
			:row-attrs="rowAttrs"
			empty-title="No mandates yet"
			empty-text="Record the first mandate to start a Dossier."
			empty-icon="lucide-file-signature"
			testid="sellos-mandate-list"
			row-testid="sellos-mandate-row"
			loading-testid="sellos-mandate-loading"
			empty-testid="sellos-mandate-empty"
		>
			<template #cell-lead_title="{ row }">
				<span class="block" data-testid="sellos-mandate-title">{{ row.lead_title }}</span>
			</template>
			<template #cell-status="{ row }">
				<StatusBadge
					:tone="row.status === 'Signed' ? 'success' : 'warning'"
					:label="row.status"
					data-testid="sellos-mandate-status"
				/>
			</template>
			<template #cell-signing="{ row }">
				<SigningBadge :status="row.signing_status" />
				<a
					v-if="row.signed_document && row.status === 'Signed'"
					:href="row.signed_document"
					target="_blank"
					rel="noopener"
					class="mt-1 block ui-link ui-text-small"
					data-testid="sellos-mandate-signed-copy"
					@click.stop
					>Download signed copy</a
				>
			</template>
			<template #cell-terms="{ row }">
				<span class="ui-text-secondary" data-testid="sellos-mandate-terms">
					{{ row.mandate_type }}, {{ row.term_months }} months from
					{{ formatDate(row.start_date) }}, fee {{ row.fee_percent }}%
				</span>
			</template>
			<template #cell-manage="{ row }">
				<AppButton
					type="button"
					data-testid="sellos-mandate-manage"
					@click="manageName = row.name"
				>
					{{ row.status === "Signed" ? "Dossier" : "Sign and Dossier" }}
				</AppButton>
			</template>
		</DataTable>

		<!-- Signing and the Private Sale Dossier: a drawer opened from the row, never controls inside the row. -->
		<FormDrawer
			:open="Boolean(current)"
			:title="current ? `Mandate for ${current.lead_title}` : 'Mandate'"
			text="Sign the mandate with the signed document, then keep notes and files in its Private Sale Dossier."
			submit-label="Done"
			testid="sellos-mandate-drawer"
			submit-testid="sellos-mandate-drawer-done"
			@close="manageName = ''"
			@submit="manageName = ''"
		>
			<template v-if="current">
				<SectionCard title="Signature">
					<div v-if="current.status !== 'Signed'">
						<p class="mb-ui-sm ui-text-muted">
							Upload the signed document to sign this mandate. It is required.
						</p>
						<FileField
							label="Signed document"
							accept=".pdf,.png,.jpg,.jpeg"
							required
							:hint="`A ${fileTypes} file of up to ${fileLimit} MB.`"
							data-testid="sellos-mandate-sign-file"
							@change="(e) => sign(current, e)"
						/>
					</div>
					<p v-else class="ui-text-muted" data-testid="sellos-mandate-signed">
						Signed on {{ formatWhen(current.signed_on) }} (recorded by
						{{ current.signed_by_name }}). Its terms are kept.
					</p>
				</SectionCard>
				<SectionCard title="Private Sale Dossier">
					<p
						v-if="!current.dossier_released"
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
							@click="open(current)"
						>
							Open the Dossier ({{ current.dossier_count }})
						</AppButton>
					</div>
					<div
						v-if="dossier[current.name]"
						class="mt-ui-sm space-y-ui-sm"
						data-testid="sellos-mandate-dossier"
					>
						<ul class="space-y-1">
							<li v-if="!dossier[current.name].items.length">
								The Dossier is empty.
							</li>
							<li
								v-for="(i, n) in dossier[current.name].items"
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
									class="underline"
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
								v-for="(v, n) in dossier[current.name].views"
								:key="n"
								data-testid="sellos-mandate-view"
							>
								{{ v.viewed_by_name }}, {{ formatWhen(v.viewed_on) }}
							</li>
						</ul>
					</div>
					<div class="mt-ui-md grid gap-ui-sm">
						<FormField
							v-model="noteTitle[current.name]"
							label="Note title"
							data-testid="sellos-mandate-note-title"
							@keydown.enter.prevent
						/>
						<FormField
							v-model="noteText[current.name]"
							type="textarea"
							label="Note"
							data-testid="sellos-mandate-note-text"
						/>
						<div class="flex flex-wrap items-end gap-ui-sm">
							<AppButton
								type="button"
								data-testid="sellos-mandate-note-add"
								@click="addNote(current)"
							>
								Add note
							</AppButton>
							<FileField
								label="Add a file to the Dossier"
								accept=".pdf,.png,.jpg,.jpeg"
								data-testid="sellos-mandate-dossier-file"
								@change="(e) => addFile(current, e)"
							/>
						</div>
					</div>
				</SectionCard>
				<p
					v-if="error"
					role="alert"
					data-testid="sellos-mandate-error"
					class="ui-text-error"
				>
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
			</template>
		</FormDrawer>

		<!-- Recording a mandate is a drawer: nothing is an open form under the list. -->
		<FormDrawer
			:open="creating"
			title="Record a mandate"
			text="It starts as a draft and is signed by uploading the signed document."
			submit-label="Record mandate"
			testid="sellos-mandate-form"
			submit-testid="sellos-mandate-save"
			@close="closeForm"
			@submit="save"
		>
			<FormSection title="Mandate">
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
			</FormSection>
			<p v-if="error" role="alert" data-testid="sellos-mandate-error" class="ui-text-error">
				{{ error }}
			</p>
		</FormDrawer>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import FileField from "../components/FileField.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import BulkBar from "../components/BulkBar.vue";
import FilterBar from "../components/FilterBar.vue";
import SigningBadge from "../components/SigningBadge.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import SectionCard from "../components/SectionCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { readFileBase64 } from "../company/partnersApi";
import { serverMessage } from "../crm/crmApi";
import { mandateApi } from "../crm/mandatesApi";
import { session } from "../session";
import { formatDate, formatWhen } from "../format";

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
const creating = ref(false);
const manageName = ref("");
const router = useRouter();
const isAdmin = computed(() => session.roles.includes("SellOS Company Admin"));
const selected = ref([]);
const bulkNotice = ref("");
async function bulkArchive() {
	error.value = "";
	bulkNotice.value = "";
	let done = 0;
	try {
		for (const name of selected.value) {
			await mandateApi.setArchived(name, 1);
			done += 1;
		}
	} catch (e) {
		error.value = serverMessage(e, "A mandate could not be archived.");
	}
	bulkNotice.value = `${done} mandates archived. Nothing is deleted.`;
	selected.value = [];
	await load();
}
const rowActions = (m) => [
	{ label: "Open mandate", onClick: () => router.push(`/crm/mandates/${m.name}`) },
	{ label: "Open the seller", onClick: () => router.push(`/crm/sellers/${m.lead}`) },
];
const search = ref("");
const statusFilter = ref("");
const signingFilter = ref("");
const typeFilter = ref("");
const current = computed(() => mandates.value.find((m) => m.name === manageName.value) || null);
const statusOptions = [
	{ label: "All statuses", value: "" },
	{ label: "Signed", value: "Signed" },
	{ label: "Draft", value: "Draft" },
];
const signingOptions = [
	{ label: "Any signing state", value: "" },
	...["Not sent", "Sent", "Viewed", "Signed", "Declined", "Expired"].map((s) => ({
		label: s,
		value: s,
	})),
];
const typeFilterOptions = [
	{ label: "Any type", value: "" },
	{ label: "Exclusive", value: "Exclusive" },
	{ label: "Open", value: "Open" },
];
const shownMandates = computed(() => {
	const q = search.value.trim().toLowerCase();
	return mandates.value.filter(
		(m) =>
			(!q || (m.lead_title || "").toLowerCase().includes(q)) &&
			(!statusFilter.value || m.status === statusFilter.value) &&
			(!signingFilter.value || m.signing_status === signingFilter.value) &&
			(!typeFilter.value || m.mandate_type === typeFilter.value)
	);
});
const chips = computed(() => [
	...(search.value ? [{ key: "search", label: `Seller: ${search.value}` }] : []),
	...(statusFilter.value ? [{ key: "status", label: `Status: ${statusFilter.value}` }] : []),
	...(signingFilter.value ? [{ key: "signing", label: `Signing: ${signingFilter.value}` }] : []),
	...(typeFilter.value ? [{ key: "type", label: `Type: ${typeFilter.value}` }] : []),
]);
function clearFilters() {
	search.value = "";
	statusFilter.value = "";
	signingFilter.value = "";
	typeFilter.value = "";
}
function removeChip(key) {
	if (key === "search") search.value = "";
	else if (key === "signing") signingFilter.value = "";
	else if (key === "type") typeFilter.value = "";
	else statusFilter.value = "";
}

const kpis = computed(() => {
	const rows = mandates.value;
	return [
		{
			label: "Mandates",
			value: rows.length,
			caption: "recorded so far",
			icon: "lucide-file-signature",
		},
		{
			label: "Signed",
			value: rows.filter((m) => m.status === "Signed").length,
			caption: "Dossier released",
			icon: "lucide-badge-check",
			tone: "success",
		},
		{
			label: "Awaiting signature",
			value: rows.filter((m) => m.status !== "Signed").length,
			caption: "drafts waiting for the signed document",
			icon: "lucide-clock",
			tone: "warning",
		},
	];
});

const columns = [
	{ key: "lead_title", label: "Seller", primary: true, sortable: true },
	{ key: "status", label: "Status", sortable: true },
	{ key: "signing", label: "Signing", sortable: true, sortValue: (m) => m.signing_status },
	{ key: "terms", label: "Terms", wrap: true, class: "min-w-[12rem]" },
	{ key: "manage", label: "Signature and Dossier", wrap: true },
];
const rowAttrs = (m) => ({
	"data-title": m.lead_title,
	"data-status": m.status,
});

function openForm() {
	error.value = "";
	creating.value = true;
}
function closeForm() {
	error.value = "";
	creating.value = false;
}

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
			creating.value = false;
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
