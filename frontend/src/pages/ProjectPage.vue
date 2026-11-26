<template>
	<PageTemplate shape="record" data-testid="sellos-project-page">
		<template #header>
			<RecordHeader
				:title="project ? project.project_name : 'Project'"
				:line="
					project
						? [
								project.developer,
								[project.locality, project.city].filter(Boolean).join(', '),
						  ]
								.filter(Boolean)
								.join(', ')
						: ''
				"
				:back-to="{ name: 'inventory' }"
				back-label="Back to inventory"
			>
				<template v-if="project" #status>
					<StatusBadge tone="neutral" :label="project.project_status" />
				</template>
				<template #actions>
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
				</template>
			</RecordHeader>
		</template>

		<template v-if="project" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-project-stats" />
		</template>

		<template #tabs>
			<PageTabs v-model="tab" :tabs="tabs" label="Project sections" />
		</template>

		<p
			v-if="error"
			role="alert"
			data-testid="sellos-project-error"
			class="mb-ui-md ui-text-error"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-project-notice"
			class="mb-ui-md ui-text-small"
		>
			{{ notice }}
		</p>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-project-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<template v-if="tab === 'units'">
			<UnitGrid v-if="project" :project="route.params.name" :refresh="units" />

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
				:actions="unitActions"
				empty-title="No units yet"
				empty-text="Add the first unit."
				empty-icon="lucide-door-open"
				testid="sellos-project-units"
				row-testid="sellos-unit-row"
			>
				<template #cell-unit_number="{ row }">
					<NameCell :name="String(row.unit_number)" data-testid="sellos-unit-number" />
				</template>
				<template #cell-status="{ row }">
					<StatusBadge
						:tone="STATUS_TONE[row.status] || 'neutral'"
						:label="row.status"
						data-testid="sellos-unit-status"
					/>
				</template>
				<template #cell-configuration="{ row }">
					<CellText :value="row.configuration" />
					<CellText
						muted
						:value="
							[
								`${row.carpet_area} sq ft`,
								row.floor === null || row.floor === undefined || row.floor === ''
									? ''
									: `floor ${row.floor}`,
								`${row.parking} parking`,
							]
								.filter(Boolean)
								.join(', ')
						"
					/>
				</template>
			</DataTable>

			<!-- Marking a unit Held, Sold and so on: a small drawer with the optional reason. -->
			<FormDrawer
				:open="Boolean(changing)"
				:title="
					changing
						? `Mark unit ${changing.row.unit_number} ${changing.status}`
						: 'Mark unit'
				"
				text="The reason is kept in the unit's status log."
				:submit-label="changing ? `Mark ${changing.status}` : 'Mark'"
				:busy="saving"
				testid="sellos-unit-status-form"
				submit-testid="sellos-unit-status-save"
				@close="changing = null"
				@submit="confirmStatus"
			>
				<FormSection title="Status">
					<FormField
						v-model="changeReason"
						label="Reason (optional)"
						data-testid="sellos-unit-reason"
					/>
				</FormSection>
			</FormDrawer>

			<!-- The status log of one unit, from the row menu. -->
			<FormDrawer
				:open="Boolean(logging)"
				:title="logging ? `Status log: unit ${logging.unit_number}` : 'Status log'"
				submit-label="Done"
				testid="sellos-unit-log-drawer"
				submit-testid="sellos-unit-log-done"
				@close="logging = null"
				@submit="logging = null"
			>
				<ul class="space-y-1 ui-text-muted" data-testid="sellos-unit-log">
					<li
						v-for="(l, i) in logging ? logging.log : []"
						:key="i"
						data-testid="sellos-unit-log-row"
					>
						{{ formatWhen(l.changed_on) }}: {{ l.changed_by_name }}
						<span v-if="l.from_status">moved it from {{ l.from_status }} to</span>
						<span v-else>set it</span>
						{{ l.to_status }}<span v-if="l.reason"> ({{ l.reason }})</span>
					</li>
				</ul>
			</FormDrawer>
		</template>

		<ProjectStructure
			v-if="project && tab === 'structure'"
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

		<ProjectPricing v-if="project && tab === 'pricing'" :project="route.params.name" />

		<template #side>
			<SectionCard v-if="project" title="Project" data-testid="sellos-project-summary">
				<dl>
					<FieldGrid :columns="1">
						<ReadField label="Developer" :value="project.developer" />
						<ReadField label="RERA number">
							<span class="ui-text-body" data-testid="sellos-project-rera">{{
								project.rera_number
							}}</span>
						</ReadField>
						<ReadField
							label="Location"
							:value="[project.locality, project.city].filter(Boolean).join(', ')"
						/>
						<ReadField label="Possession">
							<span class="ui-text-body" data-testid="sellos-project-possession">{{
								formatDate(project.possession_date) || "Not filled in"
							}}</span>
						</ReadField>
					</FieldGrid>
				</dl>
			</SectionCard>
			<SectionCard v-if="project" title="Units">
				<p class="ui-text-muted" data-testid="sellos-project-counts">
					{{ project.units.total }} units: {{ project.units.Available }} available,
					{{ project.units.Held }} held, {{ project.units.Booked }} booked,
					{{ project.units.Sold }} sold, {{ project.units.Blocked }} blocked.
				</p>
			</SectionCard>
			<SectionCard v-else title="Project">
				<LoadingSkeleton :rows="3" label="Loading the project." />
			</SectionCard>
		</template>

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
				class="ui-text-error"
				data-testid="sellos-unit-form-error"
			>
				{{ error }}
			</p>
		</FormDrawer>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import AppButton from "../components/AppButton.vue";
import CellText from "../components/CellText.vue";
import DataTable from "../components/DataTable.vue";
import FieldGrid from "../components/FieldGrid.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import KpiStrip from "../components/KpiStrip.vue";
import NameCell from "../components/NameCell.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageTabs from "../components/PageTabs.vue";
import PageTemplate from "../components/PageTemplate.vue";
import ReadField from "../components/ReadField.vue";
import RecordHeader from "../components/RecordHeader.vue";
import SectionCard from "../components/SectionCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { formatDate, formatWhen } from "../format";
import { inventoryApi, STATUS_TONE } from "../inventory/inventoryApi";
import ProjectPricing from "../inventory/ProjectPricing.vue";
import ProjectStructure from "../inventory/ProjectStructure.vue";
import UnitGrid from "../inventory/UnitGrid.vue";

// One project and its units (SOS-P4-01). Every change is made on the server and the project read back.
const route = useRoute();
const router = useRouter();
const project = ref(null);
const units = ref([]);
const statuses = ref([]);
const configurations = ref([]);
const canEdit = ref(false);
const error = ref("");
const notice = ref("");
const loadError = ref("");
const loaded = ref(false);
const unitOpen = ref(false);
const tab = ref("units");
const tabs = [
	{ key: "units", label: "Units" },
	{ key: "structure", label: "Structure" },
	{ key: "pricing", label: "Pricing" },
];
// A link or a test may open a tab: ?tab=structure or ?tab=pricing.
if (tabs.some((t) => t.key === route.query.tab)) tab.value = route.query.tab;
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
const columns = [
	{ key: "unit_number", label: "Unit", primary: true, sortable: true },
	{ key: "status", label: "Status", sortable: true },
	{ key: "configuration", label: "Configuration and area", sortable: true, wrap: true },
];
// Every unit action is in the row menu (docs/DESIGN_SYSTEM.md, "Lists", rule c).
const changing = ref(null);
const changeReason = ref("");
const logging = ref(null);
const unitActions = (row) => [
	...(canEdit.value
		? [
				{
					label: "Cost sheet",
					onClick: () => router.push({ name: "cost-sheet", params: { unit: row.name } }),
				},
				...otherStatuses(row.status).map((s) => ({
					label: `Mark ${s}`,
					onClick: () => {
						changeReason.value = "";
						changing.value = { row, status: s };
					},
				})),
		  ]
		: []),
	{ label: "Status log", onClick: () => (logging.value = row) },
];
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

const confirmStatus = async () => {
	const { row, status } = changing.value;
	const done = await act(
		() => inventoryApi.setStatus("Unit", row.name, status, changeReason.value || ""),
		`Unit ${row.unit_number} is now ${status}.`
	);
	if (done) changing.value = null;
};

onMounted(load);
</script>
