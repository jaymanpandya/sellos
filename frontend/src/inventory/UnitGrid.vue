<template>
	<section data-testid="sellos-unit-grid">
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-grid-error"
			class="mb-ui-md text-sm text-accent"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-grid-notice"
			class="mb-ui-md text-sm text-ink"
		>
			{{ notice }}
		</p>

		<ListCard title="Availability">
			<div class="mb-ui-md flex flex-wrap items-end gap-ui-md">
				<FormField
					v-model="filters.configuration"
					type="select"
					label="Configuration"
					:options="withAny('Any configuration', grid.configurations)"
					class="w-56"
					data-testid="sellos-grid-filter-configuration"
					@update:model-value="load"
				/>
				<FormField
					v-model="filters.status"
					type="select"
					label="Status"
					:options="withAny('Any status', grid.legend)"
					class="w-56"
					data-testid="sellos-grid-filter-status"
					@update:model-value="load"
				/>
			</div>
			<ul class="mb-ui-md flex flex-wrap gap-ui-sm" data-testid="sellos-grid-legend">
				<li v-for="s in grid.legend" :key="s">
					<StatusBadge
						:tone="STATUS_TONE[s]"
						:label="`${s} ${grid.counts[s] ?? 0}`"
						data-testid="sellos-grid-legend-item"
						:data-status="s"
					/>
				</li>
			</ul>
			<EmptyState
				v-if="loaded && !grid.towers.length && !grid.other_units.length"
				title="No units to show"
				text="Add towers and units to the project, or clear the filters."
				icon="lucide-building"
			/>
			<div
				v-for="t in grid.towers"
				:key="t.name"
				class="mb-ui-md rounded-card border border-line-soft p-ui-md"
				data-testid="sellos-grid-tower"
				:data-tower="t.tower_name"
			>
				<h3 class="mb-ui-sm font-medium text-ink">{{ t.tower_name }}</h3>
				<div
					v-for="f in t.floors"
					:key="f.floor_number ?? 'other'"
					class="mb-ui-sm flex flex-wrap items-center gap-ui-sm"
					data-testid="sellos-grid-floor"
					:data-floor="f.floor_number"
				>
					<span class="w-20 text-sm text-ink">{{
						f.floor_number === null ? f.floor_label : `Floor ${f.floor_number}`
					}}</span>
					<span v-if="!f.units.length" class="text-sm text-ink-muted">No units</span>
					<UnitCell v-for="u in f.units" :key="u.name" :unit="u" @pick="pick" />
				</div>
			</div>
			<div
				v-if="grid.other_units.length"
				class="mb-ui-md flex flex-wrap items-center gap-ui-sm"
				data-testid="sellos-grid-other"
			>
				<span class="w-20 text-sm text-ink">Units</span>
				<UnitCell v-for="u in grid.other_units" :key="u.name" :unit="u" @pick="pick" />
			</div>
		</ListCard>

		<div v-if="picked" class="ui-card mt-ui-md" data-testid="sellos-grid-detail">
			<h2 class="ui-card-heading mb-ui-sm">Unit {{ picked.unit_number }}</h2>
			<p class="text-sm text-ink-muted" data-testid="sellos-grid-detail-status">
				{{ picked.status
				}}<template v-if="picked.configuration"> , {{ picked.configuration }}</template
				>, {{ picked.carpet_area }} sq ft.
			</p>
			<p
				v-if="picked.status === 'Held'"
				class="text-sm text-ink"
				data-testid="sellos-grid-detail-holder"
			>
				Held by {{ picked.held_by_name }} until {{ picked.held_until }}.
				<template v-if="picked.lead_name">For {{ picked.lead_name }}.</template>
			</p>
			<p
				v-if="picked.status === 'Blocked' && picked.blocked_reason"
				class="text-sm text-ink"
				data-testid="sellos-grid-detail-reason"
			>
				Blocked: {{ picked.blocked_reason }}
			</p>

			<SuitedLeads v-if="picked.status === 'Available'" kind="unit" :name="picked.name" />

			<div v-if="picked.can_hold && grid.can_hold" class="mt-ui-md">
				<FormField
					v-model="holdLead"
					type="select"
					label="Hold for lead"
					:options="leadOptions"
					:hint="`The hold lasts ${grid.hold_hours} hours.`"
					class="w-96"
					data-testid="sellos-grid-hold-lead"
				/>
				<AppButton
					type="button"
					variant="primary"
					class="mt-ui-sm"
					data-testid="sellos-grid-hold"
					@click="hold"
				>
					Hold unit
				</AppButton>
			</div>
			<div v-if="picked.can_release" class="mt-ui-md">
				<AppButton type="button" data-testid="sellos-grid-release" @click="release">
					Release hold
				</AppButton>
			</div>
			<div v-if="picked.can_block || picked.can_unblock" class="mt-ui-md">
				<FormField
					v-model="reason"
					:label="picked.can_block ? 'Reason for blocking' : 'Reason for unblocking'"
					class="w-96"
					data-testid="sellos-grid-reason"
				/>
				<AppButton
					v-if="picked.can_block"
					type="button"
					class="mt-ui-sm"
					data-testid="sellos-grid-block"
					@click="block"
				>
					Block from sale
				</AppButton>
				<AppButton
					v-if="picked.can_unblock"
					type="button"
					class="mt-ui-sm"
					data-testid="sellos-grid-unblock"
					@click="unblock"
				>
					Unblock
				</AppButton>
			</div>
		</div>

		<div v-if="grid.can_block" class="ui-card mt-ui-md" data-testid="sellos-grid-settings">
			<h2 class="ui-card-heading mb-ui-md">Unit hold hours</h2>
			<div class="flex flex-wrap items-end gap-ui-sm">
				<FormField
					v-model="hours"
					type="number"
					label="Hours a hold lasts"
					class="w-56"
					data-testid="sellos-grid-hours"
				/>
				<AppButton type="button" data-testid="sellos-grid-hours-save" @click="saveHours">
					Save hours
				</AppButton>
			</div>
		</div>
	</section>
</template>

<script setup>
import { computed, defineComponent, h, reactive, ref, watch } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import SuitedLeads from "./SuitedLeads.vue";
import { gridApi, STATUS_TONE } from "./inventoryApi";

// The availability grid of one project (SOS-P7-06): each tower's floors and units by status, a legend,
// filters, and holding, releasing and blocking a unit. Every change is made on the server, which answers
// with the grid again. `refresh` changes when the page's units change, so the grid reads again.
const props = defineProps({
	project: { type: String, required: true },
	refresh: { type: [Array, Number, String], default: 0 },
});

const blank = () => ({
	towers: [],
	other_units: [],
	counts: {},
	legend: ["Available", "Held", "Booked", "Sold", "Blocked"],
	configurations: [],
	hold_hours: 48,
	can_hold: false,
	can_block: false,
	leads: [],
});
const grid = reactive(blank());
const filters = reactive({ configuration: "", status: "" });
const loaded = ref(false);
const error = ref("");
const notice = ref("");
const pickedName = ref("");
const holdLead = ref("");
const reason = ref("");
const hours = ref("");

const withAny = (label, values) => [{ label, value: "" }, ...values];
const leadOptions = computed(() =>
	grid.leads.map((l) => ({ label: l.lead_title || l.name, value: l.name }))
);
const allUnits = computed(() => [
	...grid.towers.flatMap((t) => t.floors.flatMap((f) => f.units)),
	...grid.other_units,
]);
const picked = computed(() => allUnits.value.find((u) => u.name === pickedName.value) || null);

// One unit: its number over a status badge, so the colour is never the only sign. A cell is a button.
const UnitCell = defineComponent({
	props: { unit: { type: Object, required: true } },
	emits: ["pick"],
	setup(cellProps, { emit }) {
		return () =>
			h(
				AppButton,
				{
					type: "button",
					"data-testid": "sellos-grid-unit",
					"data-number": cellProps.unit.unit_number,
					"data-status": cellProps.unit.status,
					onClick: () => emit("pick", cellProps.unit),
				},
				() => [
					`${cellProps.unit.unit_number} `,
					h(StatusBadge, {
						tone: STATUS_TONE[cellProps.unit.status] || "neutral",
						label: cellProps.unit.status,
					}),
					cellProps.unit.held_by_name ? ` ${cellProps.unit.held_by_name}` : "",
				]
			);
	},
});

function take(data) {
	Object.assign(grid, data);
	hours.value = String(data.hold_hours);
}

async function load() {
	try {
		take(await gridApi.grid(props.project, filters.configuration, filters.status));
		error.value = "";
	} catch (e) {
		error.value = serverMessage(e, "The grid could not be loaded.");
	} finally {
		loaded.value = true;
	}
}

function pick(unit) {
	pickedName.value = unit.name;
	holdLead.value = "";
	reason.value = "";
	error.value = "";
	notice.value = "";
}

async function act(action, message, fallback) {
	error.value = "";
	notice.value = "";
	try {
		await action();
		await load();
		notice.value = message;
	} catch (e) {
		error.value = serverMessage(e, fallback);
		await load();
	}
}

const hold = () =>
	act(
		() => gridApi.hold(pickedName.value, holdLead.value),
		"The unit is held.",
		"The unit could not be held. Choose a lead."
	);
const release = () =>
	act(
		() => gridApi.release(pickedName.value),
		"The hold is released.",
		"The hold could not be released."
	);
const block = () =>
	act(
		() => gridApi.block(pickedName.value, reason.value),
		"The unit is blocked.",
		"The unit could not be blocked."
	);
const unblock = () =>
	act(
		() => gridApi.unblock(pickedName.value, reason.value),
		"The unit is on sale again.",
		"The unit could not be unblocked."
	);
const saveHours = () =>
	act(
		() => gridApi.saveHours(hours.value),
		"The hold hours are saved.",
		"The hold hours could not be saved."
	);

watch(() => [props.project, props.refresh], load, { immediate: true });
</script>
