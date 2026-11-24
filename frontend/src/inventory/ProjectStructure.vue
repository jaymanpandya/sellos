<template>
	<section data-testid="sellos-structure">
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-structure-error"
			class="mb-ui-md text-sm text-accent"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-structure-notice"
			class="mb-ui-md text-sm text-ink"
		>
			{{ notice }}
		</p>

		<ListCard title="Towers and floors">
			<EmptyState
				v-if="!towers.length"
				title="No towers or wings yet"
				text="Add a tower or wing below, then its floors and units."
				icon="lucide-building"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-structure-towers">
				<li
					v-for="t in towers"
					:key="t.name"
					data-testid="sellos-tower-row"
					:data-name="t.name"
					:data-tower="t.tower_name"
					class="rounded-card border border-line-soft p-ui-md"
				>
					<div class="flex flex-wrap items-center gap-3">
						<span class="font-medium text-ink" data-testid="sellos-tower-name">{{
							t.tower_name
						}}</span>
						<span class="text-sm text-ink-muted" data-testid="sellos-tower-count">
							{{ t.floors.length }} floors, {{ t.unit_count }} units
						</span>
						<AppButton
							v-if="canEdit"
							type="button"
							data-testid="sellos-tower-remove"
							@click="removeTower(t)"
						>
							Remove tower
						</AppButton>
					</div>
					<ul class="mt-ui-sm space-y-1">
						<li
							v-for="f in t.floors"
							:key="f.floor_number"
							data-testid="sellos-floor-row"
							:data-floor="f.floor_number"
							class="flex flex-wrap items-center gap-2 text-sm text-ink-muted"
						>
							<span class="w-20 text-ink">Floor {{ f.floor_number }}</span>
							<StatusBadge
								v-for="u in f.units"
								:key="u.name"
								:tone="STATUS_TONE[u.status] || 'neutral'"
								:label="`${u.unit_number} ${u.status}`"
								data-testid="sellos-floor-unit"
								:data-number="u.unit_number"
							/>
							<span v-if="!f.units.length">No units yet</span>
							<AppButton
								v-if="canEdit"
								type="button"
								data-testid="sellos-floor-remove"
								@click="removeFloor(t, f)"
							>
								Remove floor
							</AppButton>
						</li>
					</ul>
				</li>
			</ul>
		</ListCard>

		<template v-if="canEdit">
			<form
				class="ui-card mt-ui-md"
				data-testid="sellos-tower-form"
				@submit.prevent="addTower"
			>
				<h2 class="ui-card-heading mb-ui-md">Add a tower or wing</h2>
				<div class="grid grid-cols-1 gap-x-ui-md gap-y-ui-md md:grid-cols-2">
					<FormField
						v-model="tower.name"
						label="Tower or wing"
						required
						data-testid="sellos-tower-name-input"
					/>
					<FormField
						v-model="tower.floors"
						label="Floors"
						hint="For example 1 to 20"
						data-testid="sellos-tower-floors-input"
					/>
				</div>
				<div class="mt-ui-md">
					<AppButton type="submit" variant="primary" data-testid="sellos-tower-save"
						>Add tower</AppButton
					>
				</div>
			</form>

			<form
				v-if="towers.length"
				class="ui-card mt-ui-md"
				data-testid="sellos-generate-form"
				@submit.prevent="generate"
			>
				<h2 class="ui-card-heading mb-ui-md">Make the units of a floor</h2>
				<div class="grid grid-cols-1 gap-x-ui-md gap-y-ui-md md:grid-cols-2">
					<FormField
						v-model="gen.tower"
						type="select"
						label="Tower or wing"
						required
						:options="towerOptions"
						data-testid="sellos-generate-tower"
					/>
					<FormField
						v-model="gen.floor"
						type="select"
						label="Floor"
						required
						:options="floorOptions"
						data-testid="sellos-generate-floor"
					/>
					<FormField
						v-model="gen.pattern"
						label="Unit numbers"
						hint="For example 1201 to 1208"
						required
						data-testid="sellos-generate-pattern"
					/>
					<FormField
						v-model="gen.configuration"
						type="select"
						label="Configuration"
						:options="configurations"
						data-testid="sellos-generate-configuration"
					/>
					<FormField
						v-model="gen.carpet_area"
						type="number"
						label="Carpet area (sq ft)"
						required
						data-testid="sellos-generate-area"
					/>
				</div>
				<div class="mt-ui-md">
					<AppButton type="submit" variant="primary" data-testid="sellos-generate-save"
						>Make units</AppButton
					>
				</div>
			</form>
		</template>

		<div class="ui-card mt-ui-md" data-testid="sellos-project-details">
			<h2 class="ui-card-heading mb-ui-md">Possession, amenities and brochures</h2>
			<FormField
				v-model="date"
				type="date"
				label="Possession date"
				:disabled="!canEdit"
				data-testid="sellos-possession-date"
			/>
			<fieldset class="mt-ui-md">
				<legend class="text-sm text-ink-muted">Amenities</legend>
				<p
					v-if="!amenityOptions.length"
					class="text-sm text-ink-muted"
					data-testid="sellos-amenities-empty"
				>
					The Company Admin has not added any amenities yet.
				</p>
				<div class="flex flex-wrap gap-x-ui-md">
					<AppCheckbox
						v-for="a in amenityOptions"
						:key="a"
						:model-value="chosen.includes(a)"
						:label="a"
						:disabled="!canEdit"
						data-testid="sellos-amenity-choice"
						:data-amenity="a"
						@update:model-value="toggle(a, $event)"
					/>
				</div>
			</fieldset>
			<div v-if="canEdit" class="mt-ui-md">
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-details-save"
					@click="saveDetails"
				>
					Save details
				</AppButton>
			</div>
			<div v-if="canManageAmenities" class="mt-ui-md flex flex-wrap items-end gap-ui-sm">
				<FormField
					v-model="newAmenity"
					label="New amenity"
					class="w-72"
					data-testid="sellos-amenity-input"
				/>
				<AppButton type="button" data-testid="sellos-amenity-add" @click="addAmenity">
					Add to the list
				</AppButton>
			</div>

			<h3 class="mt-ui-lg mb-ui-sm text-sm font-medium text-ink">Brochures</h3>
			<ul class="space-y-1" data-testid="sellos-brochures">
				<li
					v-for="b in brochures"
					:key="b.file"
					data-testid="sellos-brochure-row"
					class="text-sm text-ink"
				>
					<a :href="b.file" target="_blank" rel="noopener" class="underline">{{
						b.title
					}}</a>
					<AppButton
						v-if="canEdit"
						type="button"
						data-testid="sellos-brochure-remove"
						@click="removeBrochure(b)"
					>
						Remove
					</AppButton>
				</li>
			</ul>
			<div v-if="canEdit" class="mt-ui-sm grid grid-cols-1 gap-ui-md md:grid-cols-2">
				<FormField
					v-model="brochureTitle"
					label="Brochure title"
					data-testid="sellos-brochure-title"
				/>
				<FileField
					label="Brochure file"
					accept=".pdf,.png,.jpg,.jpeg"
					hint="A PDF, PNG or JPG file of up to 10 MB."
					data-testid="sellos-brochure-file"
					@change="addBrochure"
				/>
			</div>
		</div>
	</section>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";

import AppButton from "../components/AppButton.vue";
import AppCheckbox from "../components/AppCheckbox.vue";
import EmptyState from "../components/EmptyState.vue";
import FileField from "../components/FileField.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { readFileBase64 } from "../company/partnersApi";
import { serverMessage } from "../crm/crmApi";
import { STATUS_TONE, structureApi } from "./inventoryApi";

// Towers, wings, floors, the units of a floor, possession date, amenities and brochures of one project
// (SOS-P7-05). Every change is made on the server, which answers with the whole project; this component
// hands that answer up as `state` and the page shows it.
const props = defineProps({
	project: { type: String, required: true },
	towers: { type: Array, default: () => [] },
	canEdit: { type: Boolean, default: false },
	canManageAmenities: { type: Boolean, default: false },
	configurations: { type: Array, default: () => [] },
	possessionDate: { type: String, default: "" },
	amenities: { type: Array, default: () => [] },
	amenityOptions: { type: Array, default: () => [] },
	brochures: { type: Array, default: () => [] },
});
const emit = defineEmits(["state", "options"]);

const error = ref("");
const notice = ref("");
const tower = reactive({ name: "", floors: "" });
const gen = reactive({ tower: "", floor: "", pattern: "", configuration: "", carpet_area: "" });
const date = ref(props.possessionDate);
const chosen = ref([...props.amenities]);
const newAmenity = ref("");
const brochureTitle = ref("");

watch(
	() => [props.possessionDate, props.amenities],
	() => {
		date.value = props.possessionDate;
		chosen.value = [...props.amenities];
	}
);

const towerOptions = computed(() =>
	props.towers.map((t) => ({ label: t.tower_name, value: t.name }))
);
const floorOptions = computed(() => {
	const t = props.towers.find((row) => row.name === gen.tower);
	return (t ? t.floors : []).map((f) => String(f.floor_number));
});

async function act(action, message, fallback = "The change could not be saved.") {
	error.value = "";
	notice.value = "";
	try {
		const data = await action();
		if (data.amenity_options && !data.project) emit("options", data.amenity_options);
		else emit("state", data);
		notice.value = message;
		return data;
	} catch (e) {
		error.value = serverMessage(e, fallback);
		return null;
	}
}

async function addTower() {
	const name = tower.name;
	if (
		await act(
			() => structureApi.addTower(props.project, name, tower.floors),
			`${name} was added.`
		)
	) {
		tower.name = "";
		tower.floors = "";
	}
}

const removeTower = (t) =>
	act(
		() => structureApi.removeTower(t.name),
		`${t.tower_name} was removed.`,
		"The tower could not be removed."
	);
const removeFloor = (t, f) =>
	act(
		() => structureApi.removeFloor(t.name, f.floor_number),
		`Floor ${f.floor_number} was removed.`,
		"The floor could not be removed."
	);

async function generate() {
	error.value = "";
	notice.value = "";
	try {
		const data = await structureApi.generate({
			tower: gen.tower,
			floor: gen.floor,
			pattern: gen.pattern,
			carpet_area: gen.carpet_area,
			configuration: gen.configuration,
		});
		emit("state", data);
		notice.value = `${data.created.length} units made, ${data.skipped.length} already there.`;
	} catch (e) {
		error.value = serverMessage(e, "The units could not be made.");
	}
}

function toggle(name, on) {
	chosen.value = on
		? [...new Set([...chosen.value, name])]
		: chosen.value.filter((a) => a !== name);
}
const saveDetails = () =>
	act(
		() => structureApi.saveDetails(props.project, date.value || "", chosen.value),
		"The details were saved."
	);
async function addAmenity() {
	const name = newAmenity.value;
	if (await act(() => structureApi.saveAmenity(name), `${name} was added to the list.`))
		newAmenity.value = "";
}

async function addBrochure(event) {
	const file = event.target.files?.[0];
	if (!file) return;
	const done = await act(
		async () =>
			structureApi.addBrochure(
				props.project,
				brochureTitle.value,
				file.name,
				await readFileBase64(file)
			),
		"The brochure was added.",
		"The brochure could not be added."
	);
	if (done) brochureTitle.value = "";
	event.target.value = "";
}
const removeBrochure = (b) =>
	act(() => structureApi.removeBrochure(props.project, b.file), "The brochure was taken off.");
</script>
