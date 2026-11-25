<template>
	<PageTemplate data-testid="sellos-shares-page">
		<template #header>
			<PageHeader
				title="Share with partners"
				text="Choose what each channel partner firm may see: a project, all its units or chosen ones, its price list and brochures. A partner sees nothing else. A withdrawn share stops showing at once."
				icon="lucide-share-2"
			>
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-shares-new"
					@click="sharing = true"
				>
					<template #prefix
						><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
					/></template>
					Share a project
				</AppButton>
			</PageHeader>
		</template>

		<template v-if="!loadError && loaded" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-shares-stats" />
		</template>

		<template #filters>
			<FilterBar
				v-model:search="search"
				search-label="Search shares"
				search-placeholder="Search shares"
				search-testid="sellos-shares-search"
				clear-testid="sellos-shares-filter-clear"
				:active="Boolean(search || statusFilter)"
				:chips="chips"
				data-testid="sellos-shares-filters"
				@clear="clearFilters"
				@remove-chip="removeChip"
			>
				<FormField
					v-model="statusFilter"
					compact
					type="select"
					label="Status"
					:options="statusOptions"
					data-testid="sellos-shares-filter-status"
				/>
			</FilterBar>
		</template>

		<p
			v-if="error && !sharing"
			role="alert"
			data-testid="sellos-shares-error"
			class="mb-ui-md ui-text-error"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-shares-notice"
			class="mb-ui-md ui-text-small"
		>
			{{ notice }}
		</p>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-shares-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<DataTable
			v-else
			title="Shares"
			:columns="columns"
			:rows="shown"
			:loading="!loaded"
			:row-attrs="(s) => ({ 'data-status': s.status, 'data-project': s.project })"
			empty-title="Nothing is shared yet"
			empty-text="Share a project with the button above."
			empty-icon="lucide-share-2"
			testid="sellos-shares-list"
			row-testid="sellos-shares-row"
			empty-testid="sellos-shares-empty"
		>
			<template #cell-project_name="{ row: s }">
				<span class="ui-text-strong" data-testid="sellos-shares-row-project">
					{{ s.project_name }}
				</span>
			</template>
			<template #cell-firm_name="{ row: s }">
				<span data-testid="sellos-shares-row-firm">with {{ s.firm_name }}</span>
			</template>
			<template #cell-status="{ row: s }">
				<StatusBadge
					:tone="s.status === 'Active' ? 'success' : 'neutral'"
					:label="s.status"
					data-testid="sellos-shares-row-status"
				/>
			</template>
			<template #cell-what="{ row: s }">
				<p class="ui-text-muted">
					{{ s.all_units ? "All units" : `${s.units.length} chosen units` }};
					{{ s.share_price_list ? "price list" : "no price list" }};
					{{ s.brochures.length }} brochures.
					<span v-if="s.withdrawn_reason">Withdrawn: {{ s.withdrawn_reason }}</span>
				</p>
				<details class="mt-1">
					<summary class="cursor-pointer ui-text-muted">Log</summary>
					<ul class="mt-1 space-y-1 ui-text-muted">
						<li v-for="(l, i) in s.log" :key="i" data-testid="sellos-shares-log-row">
							{{ formatWhen(l.changed_on) }}: {{ l.changed_by_name }}, {{ l.action }}
							<span v-if="l.detail">({{ l.detail }})</span>
						</li>
					</ul>
				</details>
			</template>
			<template #cell-actions="{ row: s }">
				<div v-if="s.status === 'Active'" class="flex flex-wrap items-center gap-ui-sm">
					<FormField
						v-model="reasons[s.name]"
						compact
						label="Reason for a withdrawal (optional)"
						data-testid="sellos-shares-reason"
					/>
					<AppButton
						type="button"
						variant="danger"
						data-testid="sellos-shares-withdraw"
						@click="withdraw(s)"
					>
						Withdraw
					</AppButton>
				</div>
			</template>
		</DataTable>

		<!-- Sharing a project is a drawer, not a form above the list. -->
		<FormDrawer
			:open="sharing"
			title="Share a project"
			text="What the chosen firms may see of it."
			submit-label="Share"
			:busy="!form.project"
			testid="sellos-shares-form"
			submit-testid="sellos-shares-submit"
			@close="sharing = false"
			@submit="share"
		>
			<FormSection title="Project">
				<FormField
					v-model="form.project"
					type="select"
					label="Project"
					:options="projectOptions"
					class="md:col-span-2"
					data-testid="sellos-shares-project"
					@update:model-value="chooseProject"
				/>
			</FormSection>

			<template v-if="form.project">
				<FormSection title="Share with">
					<div class="space-y-ui-sm md:col-span-2" data-testid="sellos-shares-firms">
						<AppCheckbox
							v-model="form.every"
							label="Every Approved firm"
							data-testid="sellos-shares-every"
						/>
						<template v-if="!form.every">
							<AppCheckbox
								v-for="f in options.firms"
								:key="f.name"
								v-model="form.firms[f.name]"
								:label="f.firm_name"
								:data-testid="`sellos-shares-firm-${f.name}`"
							/>
							<p v-if="!options.firms.length" class="ui-text-muted">
								No firm is Approved yet.
							</p>
						</template>
					</div>
				</FormSection>

				<FormSection title="Units">
					<div class="space-y-ui-sm md:col-span-2" data-testid="sellos-shares-units">
						<AppCheckbox
							v-model="form.allUnits"
							label="All units of the project"
							data-testid="sellos-shares-all-units"
						/>
						<template v-if="!form.allUnits">
							<AppCheckbox
								v-for="u in options.units"
								:key="u.name"
								v-model="form.units[u.name]"
								:label="unitLabel(u)"
								:data-testid="`sellos-shares-unit-${u.name}`"
							/>
						</template>
					</div>
				</FormSection>

				<FormSection title="Price list and brochures">
					<div class="space-y-ui-sm md:col-span-2">
						<AppCheckbox
							v-model="form.priceList"
							:label="
								options.price_list
									? `The price list in force (${options.price_list.title})`
									: 'The price list in force (this project has none yet)'
							"
							data-testid="sellos-shares-price-list"
						/>
						<AppCheckbox
							v-for="m in options.brochures"
							:key="m.name"
							v-model="form.brochures[m.name]"
							:label="`${m.title} (${m.media_type})`"
							:data-testid="`sellos-shares-brochure-${m.name}`"
						/>
					</div>
				</FormSection>
			</template>
			<p v-if="error" role="alert" data-testid="sellos-shares-error" class="ui-text-error">
				{{ error }}
			</p>
		</FormDrawer>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import AppCheckbox from "../components/AppCheckbox.vue";
import DataTable from "../components/DataTable.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import FilterBar from "../components/FilterBar.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { partnerSharesApi } from "../company/partnerSharesApi";
import { serverMessage } from "../crm/crmApi";
import { formatWhen } from "../format";

// The Company Admin's sharing of projects with channel partner firms (SOS-P7-03). Every change is made on the
// server and the list read back, so what is shown is what is saved.
const options = ref({ projects: [], firms: [], units: [], brochures: [], price_list: null });
const shares = ref([]);
const error = ref("");
const notice = ref("");
const loadError = ref("");
const loaded = ref(false);
const sharing = ref(false);
const reasons = reactive({});
const form = reactive({
	project: "",
	every: false,
	firms: {},
	allUnits: true,
	units: {},
	priceList: false,
	brochures: {},
});

const search = ref("");
const statusFilter = ref("");
const statusOptions = computed(() => [
	{ label: "All", value: "" },
	...[...new Set(shares.value.map((r) => r.status).filter(Boolean))].map((v) => ({
		label: v,
		value: v,
	})),
]);
const shown = computed(() => {
	const q = search.value.trim().toLowerCase();
	return shares.value.filter(
		(r) =>
			(!q || `${r.project_name} ${r.firm_name || ""}`.toLowerCase().includes(q)) &&
			(!statusFilter.value || r.status === statusFilter.value)
	);
});
const chips = computed(() => [
	...(search.value ? [{ key: "search", label: `Search: ${search.value}` }] : []),
	...(statusFilter.value ? [{ key: "status", label: statusFilter.value }] : []),
]);
function clearFilters() {
	search.value = "";
	statusFilter.value = "";
}
function removeChip(key) {
	if (key === "search") search.value = "";
	else statusFilter.value = "";
}

const columns = [
	{ key: "project_name", label: "Project", primary: true, sortable: true },
	{ key: "firm_name", label: "Firm", sortable: true },
	{ key: "status", label: "Status", sortable: true },
	{ key: "what", label: "What is shared", wrap: true },
	{ key: "actions", label: "Actions", wrap: true },
];

const kpis = computed(() => [
	{
		label: "Active shares",
		value: shares.value.filter((s) => s.status === "Active").length,
		caption: "Showing to a firm now",
		icon: "lucide-share-2",
		tone: "success",
	},
	{
		label: "Withdrawn",
		value: shares.value.filter((s) => s.status !== "Active").length,
		caption: "No longer showing",
		icon: "lucide-circle-slash",
	},
	{
		label: "Approved firms",
		value: options.value.firms.length,
		caption: "May be shared with",
		icon: "lucide-handshake",
	},
]);

const projectOptions = computed(() =>
	options.value.projects.map((p) => ({ label: p.project_name, value: p.name }))
);
const unitLabel = (u) =>
	`${u.tower ? u.tower + " " : ""}${u.unit_number}, ${u.configuration || "unit"}`;
const ticked = (map) => Object.keys(map).filter((k) => map[k]);

async function load() {
	loadError.value = "";
	try {
		const data = await partnerSharesApi.options(form.project);
		options.value = data;
		shares.value = data.shares;
	} catch (e) {
		loadError.value = serverMessage(e, "The shares could not be loaded.");
	} finally {
		loaded.value = true;
	}
}

async function chooseProject() {
	Object.assign(form, {
		every: false,
		firms: {},
		allUnits: true,
		units: {},
		priceList: false,
		brochures: {},
	});
	await load();
}

async function share() {
	error.value = "";
	notice.value = "";
	const firms = form.every ? ["all"] : ticked(form.firms);
	try {
		await partnerSharesApi.share({
			project: form.project,
			firms,
			units: form.allUnits ? [] : ticked(form.units),
			sharePriceList: form.priceList,
			brochures: ticked(form.brochures),
		});
		notice.value = "The project was shared.";
		await chooseProject();
		sharing.value = false;
	} catch (e) {
		error.value = serverMessage(e, "The project could not be shared.");
	}
}

async function withdraw(s) {
	error.value = "";
	notice.value = "";
	try {
		await partnerSharesApi.withdraw(s.name, reasons[s.name] || "");
		delete reasons[s.name];
		notice.value = "The share was withdrawn.";
		await load();
	} catch (e) {
		error.value = serverMessage(e, "The share could not be withdrawn.");
	}
}

onMounted(load);
</script>
