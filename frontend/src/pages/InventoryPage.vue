<template>
	<div data-testid="sellos-inventory-page">
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
		</PageHeader>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-inventory-error"
			class="mb-ui-md text-sm text-accent"
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

		<ListCard title="Projects">
			<LoadingSkeleton v-if="!loaded && !loadError" :rows="3" />
			<EmptyState
				v-if="loaded && !loadError && !projects.length"
				title="No projects yet"
				text="Add a developer, then the first project."
				icon="lucide-building-2"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-inventory-projects">
				<li
					v-for="p in projects"
					:key="p.name"
					data-testid="sellos-inventory-project-row"
					:data-name="p.name"
					class="rounded-card border border-line-soft bg-surface-faint p-ui-md"
				>
					<div class="flex flex-wrap items-center gap-3">
						<router-link
							:to="{ name: 'project', params: { name: p.name } }"
							class="font-medium text-accent underline"
							data-testid="sellos-inventory-project-link"
						>
							{{ p.project_name }}
						</router-link>
						<span class="text-sm text-ink-muted">{{ p.developer }}</span>
						<span class="text-sm text-ink-muted" data-testid="sellos-inventory-rera">
							RERA {{ p.rera_number }}
						</span>
					</div>
					<p class="text-sm text-ink-muted">
						{{ [p.locality, p.city].filter(Boolean).join(", ") }}.
						{{ p.project_status }}.
						<span data-testid="sellos-inventory-unit-counts">
							{{ p.units.total }} units: {{ p.units.Available }} available,
							{{ p.units.Held }} held, {{ p.units.Sold }} sold.
						</span>
					</p>
				</li>
			</ul>
		</ListCard>

		<ListCard title="Secondary properties" class="mt-ui-md">
			<LoadingSkeleton v-if="!loaded && !loadError" :rows="3" />
			<EmptyState
				v-if="loaded && !loadError && !properties.length"
				title="No properties yet"
				text="Add a resale or rental property below."
				icon="lucide-home"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-inventory-properties">
				<li
					v-for="p in properties"
					:key="p.name"
					data-testid="sellos-inventory-property-row"
					:data-name="p.name"
					:data-status="p.status"
					class="rounded-card border border-line-soft bg-surface-faint p-ui-md"
				>
					<div class="flex flex-wrap items-center gap-3">
						<span class="font-medium text-ink">{{ p.title }}</span>
						<StatusBadge
							:tone="STATUS_TONE[p.status] || 'neutral'"
							:label="p.status"
							data-testid="sellos-inventory-property-status"
						/>
						<span v-if="p.rera_number" class="text-sm text-ink-muted">
							RERA {{ p.rera_number }}
						</span>
					</div>
					<p class="text-sm text-ink-muted">
						{{ p.property_type }}{{ p.configuration ? `, ${p.configuration}` : "" }},
						{{ p.carpet_area }} sq ft carpet, floor {{ p.floor ?? "-" }},
						{{ p.parking }} parking.
						{{ [p.locality, p.city].filter(Boolean).join(", ") }}.
					</p>
					<div v-if="canEdit" class="mt-ui-sm flex flex-wrap gap-ui-sm">
						<AppButton
							v-for="s in otherStatuses(p.status)"
							:key="s"
							type="button"
							:data-testid="`sellos-inventory-property-set-${s.toLowerCase()}`"
							@click="
								act(
									() => inventoryApi.setStatus('Property', p.name, s),
									`${p.title} is now ${s}.`
								)
							"
						>
							Mark {{ s }}
						</AppButton>
					</div>
					<details class="mt-ui-sm">
						<summary class="cursor-pointer text-sm text-ink-muted">Status log</summary>
						<ul class="mt-1 space-y-1 text-sm text-ink-muted">
							<li v-for="(l, i) in p.log" :key="i">
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

		<ListCard title="Developers" class="mt-ui-md">
			<LoadingSkeleton v-if="!loaded && !loadError" :rows="3" />
			<EmptyState
				v-if="loaded && !loadError && !developers.length"
				title="No developers yet"
				text="Add the first developer below."
				icon="lucide-hard-hat"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-inventory-developers">
				<li
					v-for="d in developers"
					:key="d.name"
					data-testid="sellos-inventory-developer-row"
					class="rounded-card border border-line-soft bg-surface-faint p-ui-md text-sm"
				>
					<span class="font-medium text-ink">{{ d.developer_name }}</span>
					<span v-if="d.contact_person" class="text-ink-muted">
						, {{ d.contact_person }}</span
					>
				</li>
			</ul>
		</ListCard>

		<MatchWeights />

		<template v-if="canEdit">
			<form
				class="ui-card mt-ui-md"
				data-testid="sellos-inventory-developer-form"
				@submit.prevent="addDeveloper"
			>
				<h2 class="ui-card-heading mb-ui-md">Add a developer</h2>
				<div class="grid grid-cols-1 gap-x-ui-md gap-y-ui-md md:grid-cols-2">
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
				</div>
				<div class="mt-ui-md">
					<AppButton
						type="submit"
						variant="primary"
						data-testid="sellos-inventory-developer-save"
					>
						Add developer
					</AppButton>
				</div>
			</form>

			<form
				class="ui-card mt-ui-md"
				data-testid="sellos-inventory-project-form"
				@submit.prevent="addProject"
			>
				<h2 class="ui-card-heading mb-ui-md">Add a project</h2>
				<div class="grid grid-cols-1 gap-x-ui-md gap-y-ui-md md:grid-cols-2">
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
				</div>
				<div class="mt-ui-md">
					<AppButton
						type="submit"
						variant="primary"
						data-testid="sellos-inventory-project-save"
					>
						Add project
					</AppButton>
				</div>
			</form>

			<form
				class="ui-card mt-ui-md"
				data-testid="sellos-inventory-property-form"
				@submit.prevent="addProperty"
			>
				<h2 class="ui-card-heading mb-ui-md">Add a secondary property</h2>
				<div class="grid grid-cols-1 gap-x-ui-md gap-y-ui-md md:grid-cols-2">
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
				</div>
				<div class="mt-ui-md">
					<AppButton
						type="submit"
						variant="primary"
						data-testid="sellos-inventory-property-save"
					>
						Add property
					</AppButton>
				</div>
			</form>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { inventoryApi, STATUS_TONE } from "../inventory/inventoryApi";
import MatchWeights from "../inventory/MatchWeights.vue";

// Developers, projects and secondary properties (SOS-P4-01). Every change is made on the server and the
// overview read back, so what is shown is what is saved.
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
	try {
		show(await action());
		notice.value = message;
		return true;
	} catch (e) {
		error.value = serverMessage(e, fallback);
		return false;
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
	}
};

const addProject = async () => {
	const name = project.project_name;
	if (await act(() => inventoryApi.saveProject({ ...project }), `${name} was added.`)) {
		Object.assign(project, blankProject());
	}
};

const addProperty = async () => {
	const title = property.title;
	const values = numbers(property, ["carpet_area", "floor", "parking"]);
	if (await act(() => inventoryApi.saveProperty(values), `${title} was added.`)) {
		Object.assign(property, blankProperty());
	}
};

onMounted(load);
</script>
