<template>
	<PageTemplate data-testid="sellos-inventory-page">
		<template #header>
			<PageHeader
				title="Inventory"
				text="Developers, primary projects with their RERA numbers, and secondary properties. Open a project to add its units."
				icon="lucide-building-2"
			>
				<router-link
					:to="{ name: 'listings' }"
					class="ui-link font-medium"
					data-testid="sellos-inventory-listings-link"
				>
					Listings
				</router-link>
				<template v-if="canEdit">
					<AppButton
						type="button"
						data-testid="sellos-inventory-add-developer"
						@click="openDrawer('developer')"
					>
						Add developer
					</AppButton>
					<AppButton
						type="button"
						data-testid="sellos-inventory-add-property"
						@click="openDrawer('property')"
					>
						Add property
					</AppButton>
					<AppButton
						type="button"
						variant="primary"
						data-testid="sellos-inventory-add-project"
						@click="openDrawer('project')"
					>
						<template #prefix
							><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
						/></template>
						Add project
					</AppButton>
				</template>
			</PageHeader>
		</template>

		<template v-if="loaded && !loadError" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-inventory-stats" />
		</template>

		<p
			v-if="error"
			role="alert"
			data-testid="sellos-inventory-error"
			class="mb-ui-md text-sm text-danger"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-inventory-notice"
			class="mb-ui-md text-sm text-ink"
		>
			{{ notice }}
		</p>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-inventory-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<div v-if="!loadError" class="space-y-ui-md">
			<DataTable
				title="Projects"
				caption="Projects"
				:columns="projectColumns"
				:rows="projects"
				:loading="!loaded"
				loading-label="Loading projects."
				:row-to="projectTo"
				:row-name="(p) => p.project_name"
				empty-title="No projects yet"
				empty-text="Add a developer, then the first project."
				empty-icon="lucide-building-2"
				testid="sellos-inventory-projects"
				row-testid="sellos-inventory-project-row"
			>
				<template #cell-project_name="{ row }">
					<router-link
						:to="projectTo(row)"
						class="text-ink no-underline hover:underline"
						data-testid="sellos-inventory-project-link"
					>
						{{ row.project_name }}
					</router-link>
				</template>
				<template #cell-rera_number="{ row }">
					<span data-testid="sellos-inventory-rera">RERA {{ row.rera_number }}</span>
				</template>
				<template #cell-location="{ row }">
					{{ [row.locality, row.city].filter(Boolean).join(", ") }}
				</template>
				<template #cell-project_status="{ row }">
					<StatusBadge tone="neutral" :label="row.project_status" />
				</template>
				<template #cell-units="{ row }">
					<span data-testid="sellos-inventory-unit-counts">
						{{ row.units.total }} units: {{ row.units.Available }} available,
						{{ row.units.Held }} held, {{ row.units.Sold }} sold.
					</span>
				</template>
			</DataTable>

			<DataTable
				title="Secondary properties"
				caption="Secondary properties"
				:columns="propertyColumns"
				:rows="properties"
				:loading="!loaded"
				loading-label="Loading properties."
				:actions="propertyActions"
				:row-name="(p) => p.title"
				empty-title="No properties yet"
				empty-text="Add a resale or rental property."
				empty-icon="lucide-home"
				testid="sellos-inventory-properties"
				row-testid="sellos-inventory-property-row"
			>
				<template #cell-status="{ row }">
					<StatusBadge
						:tone="STATUS_TONE[row.status] || 'neutral'"
						:label="row.status"
						:data-status="row.status"
						data-testid="sellos-inventory-property-status"
					/>
				</template>
				<template #cell-details="{ row }">
					{{ row.property_type }}{{ row.configuration ? `, ${row.configuration}` : "" }},
					floor {{ row.floor ?? "-" }}, {{ row.parking }} parking
				</template>
				<template #cell-carpet_area="{ row }">{{ row.carpet_area }} sq ft</template>
				<template #cell-location="{ row }">
					{{ [row.locality, row.city].filter(Boolean).join(", ") }}
				</template>
			</DataTable>

			<DataTable
				title="Developers"
				caption="Developers"
				:columns="developerColumns"
				:rows="developers"
				:loading="!loaded"
				loading-label="Loading developers."
				:row-name="(d) => d.developer_name"
				empty-title="No developers yet"
				empty-text="Add the first developer."
				empty-icon="lucide-hard-hat"
				testid="sellos-inventory-developers"
				row-testid="sellos-inventory-developer-row"
			/>

			<MatchWeights />
		</div>

		<!-- The status log of a secondary property. -->
		<Dialog v-model="logOpen" :options="{ title: logTitle, size: 'md' }">
			<template #body-content>
				<ul
					class="space-y-1 text-sm text-ink-muted"
					data-testid="sellos-inventory-property-log"
				>
					<li v-for="(l, i) in logRows" :key="i">
						{{ formatWhen(l.changed_on) }}: {{ l.changed_by_name }}
						<span v-if="l.from_status">moved it from {{ l.from_status }} to</span>
						<span v-else>set it</span>
						{{ l.to_status }}<span v-if="l.reason"> ({{ l.reason }})</span>
					</li>
				</ul>
			</template>
		</Dialog>

		<template v-if="canEdit">
			<FormDrawer
				:open="drawer === 'developer'"
				title="Add a developer"
				submit-label="Add developer"
				:busy="saving"
				testid="sellos-inventory-developer-form"
				submit-testid="sellos-inventory-developer-save"
				@close="drawer = ''"
				@submit="addDeveloper"
			>
				<FormSection title="Developer">
					<FormField
						v-model="developer.developer_name"
						label="Developer name"
						required
						data-testid="sellos-inventory-developer-name"
					/>
					<FormField
						v-model="developer.contact_person"
						label="Contact person"
						data-testid="sellos-inventory-developer-contact"
					/>
				</FormSection>
				<p
					v-if="error"
					role="alert"
					class="text-sm text-danger"
					data-testid="sellos-inventory-drawer-error"
				>
					{{ error }}
				</p>
			</FormDrawer>

			<FormDrawer
				:open="drawer === 'project'"
				title="Add a project"
				submit-label="Add project"
				:busy="saving"
				testid="sellos-inventory-project-form"
				submit-testid="sellos-inventory-project-save"
				@close="drawer = ''"
				@submit="addProject"
			>
				<FormSection title="Project">
					<FormField
						v-model="project.project_name"
						label="Project name"
						required
						data-testid="sellos-inventory-project-name"
					/>
					<FormField
						v-model="project.developer"
						type="select"
						label="Developer"
						required
						:options="developerOptions"
						data-testid="sellos-inventory-project-developer"
					/>
					<FormField
						v-model="project.rera_number"
						label="RERA number"
						required
						hint="As printed on the registration, for example P51800012345."
						data-testid="sellos-inventory-project-rera"
					/>
					<FormField
						v-model="project.project_status"
						type="select"
						label="Project status"
						:options="projectStatuses"
						data-testid="sellos-inventory-project-status"
					/>
				</FormSection>
				<FormSection title="Location">
					<FormField
						v-model="project.city"
						label="City"
						required
						data-testid="sellos-inventory-project-city"
					/>
					<FormField
						v-model="project.locality"
						label="Locality"
						data-testid="sellos-inventory-project-locality"
					/>
				</FormSection>
				<p
					v-if="error"
					role="alert"
					class="text-sm text-danger"
					data-testid="sellos-inventory-drawer-error"
				>
					{{ error }}
				</p>
			</FormDrawer>

			<FormDrawer
				:open="drawer === 'property'"
				title="Add a secondary property"
				submit-label="Add property"
				:busy="saving"
				testid="sellos-inventory-property-form"
				submit-testid="sellos-inventory-property-save"
				@close="drawer = ''"
				@submit="addProperty"
			>
				<FormSection title="Property">
					<FormField
						v-model="property.title"
						label="Title"
						required
						data-testid="sellos-inventory-property-title"
					/>
					<FormField
						v-model="property.property_type"
						type="select"
						label="Property type"
						required
						:options="propertyTypes"
						data-testid="sellos-inventory-property-type"
					/>
					<FormField
						v-model="property.configuration"
						type="select"
						label="Configuration"
						:options="configurations"
						data-testid="sellos-inventory-property-configuration"
					/>
					<FormField
						v-model="property.carpet_area"
						type="number"
						label="Carpet area (sq ft)"
						required
						data-testid="sellos-inventory-property-area"
					/>
					<FormField
						v-model="property.floor"
						type="number"
						label="Floor"
						data-testid="sellos-inventory-property-floor"
					/>
					<FormField
						v-model="property.parking"
						type="number"
						label="Parking slots"
						data-testid="sellos-inventory-property-parking"
					/>
					<FormField
						v-model="property.rera_number"
						label="RERA number (optional)"
						data-testid="sellos-inventory-property-rera"
					/>
				</FormSection>
				<FormSection title="Location">
					<FormField
						v-model="property.city"
						label="City"
						required
						data-testid="sellos-inventory-property-city"
					/>
					<FormField
						v-model="property.locality"
						label="Locality"
						data-testid="sellos-inventory-property-locality"
					/>
				</FormSection>
				<p
					v-if="error"
					role="alert"
					class="text-sm text-danger"
					data-testid="sellos-inventory-drawer-error"
				>
					{{ error }}
				</p>
			</FormDrawer>
		</template>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { Dialog } from "frappe-ui";

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
import { formatWhen } from "../format";
import { inventoryApi, STATUS_TONE } from "../inventory/inventoryApi";
import MatchWeights from "../inventory/MatchWeights.vue";

// Developers, projects and secondary properties (SOS-P4-01). Every change is made on the server and the
// overview read back, so what is shown is what is saved. The three add forms are drawers.
const developers = ref([]);
const projects = ref([]);
const properties = ref([]);
const statuses = ref([]);
const configurations = ref([]);
const propertyTypes = ref([]);
const projectStatuses = ref([]);
const canEdit = ref(false);
const error = ref("");
const notice = ref("");
const loadError = ref("");
const loaded = ref(false);
const drawer = ref("");
const saving = ref(false);
const logOpen = ref(false);
const logTitle = ref("");
const logRows = ref([]);

const blankDeveloper = () => ({ developer_name: "", contact_person: "" });
const blankProject = () => ({
	project_name: "",
	developer: "",
	rera_number: "",
	project_status: "Under construction",
	city: "",
	locality: "",
});
const blankProperty = () => ({
	title: "",
	property_type: "Apartment",
	configuration: "",
	carpet_area: "",
	floor: "",
	parking: "",
	rera_number: "",
	city: "",
	locality: "",
});
const developer = reactive(blankDeveloper());
const project = reactive(blankProject());
const property = reactive(blankProperty());

const developerOptions = computed(() => developers.value.map((d) => d.developer_name));
const otherStatuses = (current) => statuses.value.filter((s) => s !== current);

const kpis = computed(() => {
	const units = projects.value.reduce((n, p) => n + (p.units?.total || 0), 0);
	const available = projects.value.reduce((n, p) => n + (p.units?.Available || 0), 0);
	return [
		{
			label: "Projects",
			value: projects.value.length,
			caption: "primary projects",
			icon: "lucide-building-2",
		},
		{
			label: "Units",
			value: units,
			caption: "across all projects",
			icon: "lucide-layout-grid",
		},
		{
			label: "Available units",
			value: available,
			caption: "ready to sell",
			icon: "lucide-door-open",
			tone: "success",
		},
		{
			label: "Secondary properties",
			value: properties.value.length,
			caption: "resale and rental",
			icon: "lucide-home",
		},
	];
});

const projectTo = (p) => ({ name: "project", params: { name: p.name } });
const projectColumns = [
	{ key: "project_name", label: "Project", primary: true, sortable: true },
	{ key: "developer", label: "Developer", sortable: true },
	{ key: "rera_number", label: "RERA number" },
	{ key: "location", label: "Location", wrap: true },
	{ key: "project_status", label: "Status", sortable: true },
	{ key: "units", label: "Units", wrap: true },
];
const propertyColumns = [
	{ key: "title", label: "Property", primary: true, sortable: true },
	{ key: "status", label: "Status", sortable: true },
	{ key: "details", label: "Details", wrap: true },
	{
		key: "carpet_area",
		label: "Carpet area",
		align: "right",
		sortable: true,
		sortValue: (p) => Number(p.carpet_area || 0),
	},
	{ key: "location", label: "Location", wrap: true },
	{ key: "rera_number", label: "RERA number" },
];
const developerColumns = [
	{ key: "developer_name", label: "Developer", primary: true, sortable: true },
	{ key: "contact_person", label: "Contact person" },
];

function propertyActions(p) {
	const out = [];
	if (canEdit.value) {
		for (const s of otherStatuses(p.status)) {
			out.push({
				label: `Mark ${s}`,
				onClick: () =>
					act(
						() => inventoryApi.setStatus("Property", p.name, s),
						`${p.title} is now ${s}.`
					),
			});
		}
	}
	out.push({
		label: "Status log",
		onClick: () => {
			logTitle.value = `Status log: ${p.title}`;
			logRows.value = p.log || [];
			logOpen.value = true;
		},
	});
	return out;
}

function openDrawer(kind) {
	error.value = "";
	drawer.value = kind;
}

function show(data) {
	developers.value = data.developers;
	projects.value = data.projects;
	properties.value = data.properties;
	statuses.value = data.statuses;
	configurations.value = data.configurations;
	propertyTypes.value = data.property_types;
	projectStatuses.value = data.project_statuses;
	canEdit.value = data.can_edit;
}

async function load() {
	loadError.value = "";
	try {
		show(await inventoryApi.overview());
	} catch (e) {
		loadError.value = serverMessage(e, "The inventory could not be loaded.");
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

// A number box gives "" when empty; the server wants a number or nothing.
const numbers = (values, keys) => {
	const out = { ...values };
	for (const key of keys) if (out[key] === "" || out[key] === null) delete out[key];
	return out;
};

const addDeveloper = async () => {
	const name = developer.developer_name;
	if (await act(() => inventoryApi.saveDeveloper({ ...developer }), `${name} was added.`)) {
		Object.assign(developer, blankDeveloper());
		drawer.value = "";
	}
};

const addProject = async () => {
	const name = project.project_name;
	if (await act(() => inventoryApi.saveProject({ ...project }), `${name} was added.`)) {
		Object.assign(project, blankProject());
		drawer.value = "";
	}
};

const addProperty = async () => {
	const title = property.title;
	const values = numbers(property, ["carpet_area", "floor", "parking"]);
	if (await act(() => inventoryApi.saveProperty(values), `${title} was added.`)) {
		Object.assign(property, blankProperty());
		drawer.value = "";
	}
};

onMounted(load);
</script>
