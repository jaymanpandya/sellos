<template>
	<PageTemplate data-testid="sellos-project-page">
		<template #header>
			<PageHeader
				:title="project ? project.project_name : 'Project'"
				text="The project's RERA number and its units. Each unit has a configuration, carpet area, floor, parking and a status."
				icon="lucide-building-2"
			>
				<AppButton
					v-if="canEdit"
					type="button"
					variant="primary"
					data-testid="sellos-unit-add"
					@click="openUnitForm"
				>
					<template #prefix
						><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
					/></template>
					Add unit
				</AppButton>
			</PageHeader>
		</template>

		<template v-if="project" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-project-stats" />
		</template>

		<p
			v-if="error"
			role="alert"
			data-testid="sellos-project-error"
			class="mb-ui-md text-sm text-danger"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-project-notice"
			class="mb-ui-md text-sm text-ink"
		>
			{{ notice }}
		</p>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-project-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<div v-if="project" class="ui-card mb-ui-md" data-testid="sellos-project-summary">
			<p class="text-sm text-ink">
				<span class="font-medium">{{ project.developer }}</span
				>. RERA number:
				<span data-testid="sellos-project-rera">{{ project.rera_number }}</span
				>. {{ [project.locality, project.city].filter(Boolean).join(", ") }}.
				{{ project.project_status }}.
			</p>
			<p class="text-sm text-ink-muted" data-testid="sellos-project-counts">
				{{ project.units.total }} units: {{ project.units.Available }} available,
				{{ project.units.Held }} held, {{ project.units.Booked }} booked,
				{{ project.units.Sold }} sold, {{ project.units.Blocked }} blocked.
			</p>
			<p class="text-sm text-ink-muted" data-testid="sellos-project-possession">
				Possession: {{ formatDate(project.possession_date) || "not set" }}.
			</p>
		</div>

		<UnitGrid v-if="project" class="mb-ui-md" :project="route.params.name" :refresh="units" />

		<ProjectStructure
			v-if="project"
			class="mb-ui-md"
			:project="route.params.name"
			:towers="structure.towers"
			:can-edit="canEdit"
			:can-manage-amenities="structure.can_manage_amenities"
			:configurations="configurations"
			:possession-date="structure.possession_date"
			:amenities="structure.amenities"
			:amenity-options="structure.amenity_options"
			:brochures="structure.brochures"
			@state="show"
			@options="structure.amenity_options = $event"
		/>

		<ProjectPricing v-if="project" class="mb-ui-md" :project="route.params.name" />

		<DataTable
			title="Units"
			caption="Units"
			:columns="columns"
			:rows="units"
			:loading="!loaded && !loadError"
			loading-label="Loading units."
			:row-attrs="
				(u) => ({
					'data-number': u.unit_number,
					'data-status': u.status,
				})
			"
			:row-name="(u) => `unit ${u.unit_number}`"
			empty-title="No units yet"
			empty-text="Add the first unit."
			empty-icon="lucide-door-open"
			testid="sellos-project-units"
			row-testid="sellos-unit-row"
		>
			<template #cell-unit_number="{ row }">
				<span class="font-medium" data-testid="sellos-unit-number">{{
					row.unit_number
				}}</span>
			</template>
			<template #cell-status="{ row }">
				<StatusBadge
					:tone="STATUS_TONE[row.status] || 'neutral'"
					:label="row.status"
					data-testid="sellos-unit-status"
				/>
			</template>
			<template #cell-configuration="{ row }">
				{{ row.configuration || "No configuration" }}
			</template>
			<template #cell-carpet_area="{ row }">{{ row.carpet_area }} sq ft</template>
			<template #cell-floor="{ row }">{{ row.floor ?? "-" }}</template>
			<template #cell-cost_sheet="{ row }">
				<router-link
					:to="{ name: 'cost-sheet', params: { unit: row.name } }"
					class="ui-link text-sm font-medium"
					data-testid="sellos-unit-cost-sheet"
				>
					Cost sheet
				</router-link>
			</template>
			<template #cell-change="{ row }">
				<div class="flex flex-wrap items-end gap-ui-sm">
					<FormField
						v-model="reasons[row.name]"
						label="Reason (optional)"
						class="w-56"
						data-testid="sellos-unit-reason"
					/>
					<AppButton
						v-for="s in otherStatuses(row.status)"
						:key="s"
						type="button"
						:data-testid="`sellos-unit-set-${s.toLowerCase()}`"
						@click="changeStatus(row, s)"
					>
						Mark {{ s }}
					</AppButton>
				</div>
			</template>
			<template #cell-log="{ row }">
				<details data-testid="sellos-unit-log">
					<summary class="cursor-pointer text-sm text-ink-muted">Status log</summary>
					<ul class="mt-1 space-y-1 text-sm text-ink-muted">
						<li v-for="(l, i) in row.log" :key="i" data-testid="sellos-unit-log-row">
							{{ formatWhen(l.changed_on) }}: {{ l.changed_by_name }}
							<span v-if="l.from_status">moved it from {{ l.from_status }} to</span>
							<span v-else>set it</span>
							{{ l.to_status }}<span v-if="l.reason"> ({{ l.reason }})</span>
						</li>
					</ul>
				</details>
			</template>
		</DataTable>

		<FormDrawer
			v-if="canEdit"
			:open="unitOpen"
			title="Add a unit"
			submit-label="Add unit"
			:busy="saving"
			testid="sellos-unit-form"
			submit-testid="sellos-unit-save"
			@close="unitOpen = false"
			@submit="addUnit"
		>
			<FormSection title="Unit">
				<FormField
					v-model="unit.unit_number"
					label="Unit number"
					required
					data-testid="sellos-unit-number-input"
				/>
				<FormField
					v-model="unit.configuration"
					type="select"
					label="Configuration"
					:options="configurations"
					data-testid="sellos-unit-configuration"
				/>
				<FormField
					v-model="unit.carpet_area"
					type="number"
					label="Carpet area (sq ft)"
					required
					data-testid="sellos-unit-area"
				/>
				<FormField
					v-model="unit.floor"
					type="number"
					label="Floor"
					data-testid="sellos-unit-floor"
				/>
				<FormField
					v-model="unit.parking"
					type="number"
					label="Parking slots"
					data-testid="sellos-unit-parking"
				/>
			</FormSection>
			<p
				v-if="error"
				role="alert"
				class="text-sm text-danger"
				data-testid="sellos-unit-form-error"
			>
				{{ error }}
			</p>
		</FormDrawer>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";

import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { formatDate, formatWhen } from "../format";
import { inventoryApi, STATUS_TONE } from "../inventory/inventoryApi";
import ProjectPricing from "../inventory/ProjectPricing.vue";
import ProjectStructure from "../inventory/ProjectStructure.vue";
import UnitGrid from "../inventory/UnitGrid.vue";

// One project and its units (SOS-P4-01). Every change is made on the server and the project read back.
const route = useRoute();
const project = ref(null);
const units = ref([]);
const statuses = ref([]);
const configurations = ref([]);
const canEdit = ref(false);
const error = ref("");
const notice = ref("");
const loadError = ref("");
const loaded = ref(false);
const reasons = reactive({});
const unitOpen = ref(false);
const saving = ref(false);
// SOS-P7-05: towers, floors, possession date, amenities and brochures.
const structure = reactive({
	towers: [],
	possession_date: "",
	amenities: [],
	amenity_options: [],
	brochures: [],
	can_manage_amenities: false,
});
const blankUnit = () => ({
	unit_number: "",
	configuration: "",
	carpet_area: "",
	floor: "",
	parking: "",
});
const unit = reactive(blankUnit());

const kpis = computed(() => {
	const c = project.value?.units || {};
	return [
		{
			label: "Units",
			value: c.total ?? 0,
			caption: "in this project",
			icon: "lucide-layout-grid",
		},
		{
			label: "Available",
			value: c.Available ?? 0,
			caption: "ready to sell",
			icon: "lucide-door-open",
			tone: "success",
		},
		{
			label: "Held",
			value: c.Held ?? 0,
			caption: "on hold for a buyer",
			icon: "lucide-clock",
			tone: "warning",
		},
		{
			label: "Sold",
			value: c.Sold ?? 0,
			caption: "no longer available",
			icon: "lucide-badge-check",
		},
	];
});
const columns = computed(() => [
	{ key: "unit_number", label: "Unit", primary: true, sortable: true },
	{ key: "status", label: "Status", sortable: true },
	{ key: "configuration", label: "Configuration", sortable: true },
	{
		key: "carpet_area",
		label: "Carpet area",
		align: "right",
		sortable: true,
		sortValue: (u) => Number(u.carpet_area || 0),
	},
	{
		key: "floor",
		label: "Floor",
		align: "right",
		sortable: true,
		sortValue: (u) => Number(u.floor ?? -1),
	},
	{ key: "parking", label: "Parking", align: "right" },
	...(canEdit.value
		? [
				{ key: "cost_sheet", label: "Cost sheet" },
				{ key: "change", label: "Change status", wrap: true },
		  ]
		: []),
	{ key: "log", label: "Log", wrap: true },
]);
function openUnitForm() {
	error.value = "";
	unitOpen.value = true;
}

const otherStatuses = (current) => statuses.value.filter((s) => s !== current);

function show(data) {
	project.value = data.project;
	units.value = data.units;
	statuses.value = data.statuses;
	configurations.value = data.configurations;
	canEdit.value = data.can_edit;
	for (const key of Object.keys(structure)) if (key in data) structure[key] = data[key];
}

async function load() {
	loadError.value = "";
	try {
		show(await inventoryApi.project(route.params.name));
	} catch (e) {
		loadError.value = serverMessage(e, "The project could not be loaded.");
	} finally {
		loaded.value = true;
	}
}

async function act(action, message, fallback = "The change could not be saved.") {
	error.value = "";
	notice.value = "";
	saving.value = true;
	try {
		show(await action());
		notice.value = message;
		return true;
	} catch (e) {
		error.value = serverMessage(e, fallback);
		return false;
	} finally {
		saving.value = false;
	}
}

const addUnit = async () => {
	const values = { project: route.params.name, ...unit };
	for (const key of ["carpet_area", "floor", "parking"])
		if (values[key] === "") delete values[key];
	const number = unit.unit_number;
	if (await act(() => inventoryApi.saveUnit(values), `Unit ${number} was added.`)) {
		Object.assign(unit, blankUnit());
		unitOpen.value = false;
	}
};

const changeStatus = async (row, status) => {
	const done = await act(
		() => inventoryApi.setStatus("Unit", row.name, status, reasons[row.name] || ""),
		`Unit ${row.unit_number} is now ${status}.`
	);
	if (done) delete reasons[row.name];
};

onMounted(load);
</script>
