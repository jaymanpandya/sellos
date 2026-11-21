<template>
	<div data-testid="sellos-project-page">
		<PageHeader
			:title="project ? project.project_name : 'Project'"
			text="The project's RERA number and its units. Each unit has a configuration, carpet area, floor, parking and a status."
			icon="lucide-building-2"
		/>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-project-error"
			class="mb-ui-md text-sm text-accent"
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
				Possession: {{ project.possession_date || "not set" }}.
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

		<ListCard title="Units">
			<EmptyState
				v-if="loaded && !loadError && !units.length"
				title="No units yet"
				text="Add the first unit below."
				icon="lucide-door-open"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-project-units">
				<li
					v-for="u in units"
					:key="u.name"
					data-testid="sellos-unit-row"
					:data-name="u.name"
					:data-number="u.unit_number"
					:data-status="u.status"
					class="rounded-input border border-line-soft p-ui-md"
				>
					<div class="flex flex-wrap items-center gap-3">
						<span class="font-medium text-ink" data-testid="sellos-unit-number">
							{{ u.unit_number }}
						</span>
						<StatusBadge
							:tone="STATUS_TONE[u.status] || 'neutral'"
							:label="u.status"
							data-testid="sellos-unit-status"
						/>
						<span class="text-sm text-ink-muted">
							{{ u.configuration || "No configuration" }}, {{ u.carpet_area }} sq ft
							carpet, floor {{ u.floor ?? "-" }}, {{ u.parking }} parking
						</span>
					</div>
					<div v-if="canEdit" class="mt-ui-sm flex flex-wrap items-end gap-ui-sm">
						<FormField
							v-model="reasons[u.name]"
							label="Reason (optional)"
							class="w-72"
							data-testid="sellos-unit-reason"
						/>
						<AppButton
							v-for="s in otherStatuses(u.status)"
							:key="s"
							type="button"
							:data-testid="`sellos-unit-set-${s.toLowerCase()}`"
							@click="changeStatus(u, s)"
						>
							Mark {{ s }}
						</AppButton>
					</div>
					<details class="mt-ui-sm" data-testid="sellos-unit-log">
						<summary class="cursor-pointer text-sm text-ink-muted">Status log</summary>
						<ul class="mt-1 space-y-1 text-sm text-ink-muted">
							<li v-for="(l, i) in u.log" :key="i" data-testid="sellos-unit-log-row">
								{{ l.changed_on }}: {{ l.changed_by_name }}
								<span v-if="l.from_status"
									>moved it from {{ l.from_status }} to</span
								>
								<span v-else>set it</span>
								{{ l.to_status }}<span v-if="l.reason"> ({{ l.reason }})</span>
							</li>
						</ul>
					</details>
				</li>
			</ul>
		</ListCard>

		<form
			v-if="canEdit"
			class="ui-card mt-ui-md"
			data-testid="sellos-unit-form"
			@submit.prevent="addUnit"
		>
			<h2 class="ui-card-heading mb-ui-md">Add a unit</h2>
			<div class="grid grid-cols-1 gap-x-ui-md gap-y-ui-md md:grid-cols-2">
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
			</div>
			<div class="mt-ui-md">
				<AppButton type="submit" variant="primary" data-testid="sellos-unit-save">
					Add unit
				</AppButton>
			</div>
		</form>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { inventoryApi, STATUS_TONE } from "../inventory/inventoryApi";
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
	try {
		show(await action());
		notice.value = message;
		return true;
	} catch (e) {
		error.value = serverMessage(e, fallback);
		return false;
	}
}

const addUnit = async () => {
	const values = { project: route.params.name, ...unit };
	for (const key of ["carpet_area", "floor", "parking"])
		if (values[key] === "") delete values[key];
	const number = unit.unit_number;
	if (await act(() => inventoryApi.saveUnit(values), `Unit ${number} was added.`)) {
		Object.assign(unit, blankUnit());
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
