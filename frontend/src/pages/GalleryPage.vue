<template>
	<PageTemplate shape="form" :data-area="area" data-testid="sellos-gallery-page">
		<template #header>
			<PageHeader
				title="Design system gallery"
				text="Every shared piece in every state. Pick an area to see its colours; the brand colour changes the buttons, the sidebar highlight and the links."
				icon="lucide-palette"
			>
				<AppButton data-testid="sellos-gallery-reset" @click="reset">Reset</AppButton>
			</PageHeader>
		</template>

		<template #notice>
			<Notice title="How to read this page" data-testid="sellos-gallery-notice">
				<ul>
					<li>Each card below is one piece of docs/DESIGN_SYSTEM.md, section 2.</li>
					<li>The four themes: one for each area, and any company brand colour.</li>
				</ul>
			</Notice>
		</template>

		<SectionCard
			title="Theme"
			help="The area colours the header icon, the stat tiles and the empty state."
		>
			<FieldGrid>
				<FormField
					v-model="area"
					type="select"
					label="Area"
					:options="areaOptions"
					data-testid="sellos-gallery-area"
				/>
				<FormField
					v-model="brand"
					label="Brand colour"
					hint="A hex colour: six digits after the hash."
					data-testid="sellos-gallery-brand"
					@update:model-value="applyBrand"
				/>
			</FieldGrid>
		</SectionCard>

		<SectionCard
			title="Buttons"
			help="One height, 44px. Outline is the default; at most one solid button for an area."
		>
			<div class="flex flex-wrap items-center gap-2" data-testid="sellos-gallery-buttons">
				<AppButton variant="primary">Solid</AppButton>
				<AppButton>Outline</AppButton>
				<AppButton variant="link">Link</AppButton>
				<AppButton variant="danger">Danger</AppButton>
				<AppButton variant="danger" confirm>Confirm delete</AppButton>
				<AppButton variant="icon" label="Search">
					<span class="lucide-search icon-inherit size-4" aria-hidden="true" />
				</AppButton>
				<AppButton variant="primary" disabled>Solid, disabled</AppButton>
				<AppButton disabled>Outline, disabled</AppButton>
				<AppButton active>Pressed</AppButton>
			</div>
		</SectionCard>

		<SectionCard title="Fields" help="44px, 10px radius, a brand ring on focus.">
			<FieldGrid>
				<FormField v-model="text" label="Text field" hint="A hint under the field." />
				<FormField v-model="text" label="Required field" required />
				<FormField
					v-model="choice"
					type="select"
					label="Select"
					:options="['One', 'Two', 'Three']"
				/>
				<MoneyField v-model="money" label="Money field (Rs)" />
				<FormField v-model="agreed" type="checkbox" label="A checkbox" />
			</FieldGrid>
		</SectionCard>

		<SectionCard
			title="Status pills"
			help="Always a word and an icon with a tint, never a colour alone."
		>
			<div class="flex flex-wrap items-center gap-2" data-testid="sellos-gallery-pills">
				<StatusBadge tone="success" label="Done" />
				<StatusBadge tone="warning" label="Waiting" />
				<StatusBadge tone="danger" label="Late" />
				<StatusBadge tone="info" label="Open" />
				<StatusBadge tone="neutral" label="Draft" />
			</div>
		</SectionCard>

		<SectionCard
			title="Stat tiles"
			help="The whole tile is the link; the top bar shows the state."
		>
			<KpiStrip :items="tiles" data-testid="sellos-gallery-tiles" />
		</SectionCard>

		<SectionCard title="Read fields" help="A missing value reads Not filled in.">
			<dl>
				<FieldGrid>
					<ReadField label="Name" value="Asha Rao" />
					<ReadField label="Budget" :value="formatMoney(12500000)" />
					<ReadField label="Last contacted" :value="formatWhen('2026-11-24 11:44:00')" />
					<ReadField label="Email" value="" />
				</FieldGrid>
			</dl>
			<template #footer>
				<AppButton>Edit</AppButton>
			</template>
		</SectionCard>

		<Notice tone="warning" title="A warning notice" data-testid="sellos-gallery-warning">
			<ul>
				<li>Several notes are one notice, never separate boxes.</li>
				<li>The left edge is amber for a warning and brand for information.</li>
			</ul>
		</Notice>

		<SectionCard title="Tabs">
			<PageTabs v-model="tab" :tabs="tabs" label="Gallery tabs" />
			<p class="ui-text-secondary">The open tab: {{ tab }}.</p>
		</SectionCard>

		<SectionCard title="Table">
			<DataTable
				:columns="columns"
				:rows="rows"
				row-key="name"
				testid="sellos-gallery-table"
				row-testid="sellos-gallery-row"
			>
				<template #cell-status="{ row }"
					><StatusBadge :tone="row.tone" :label="row.status"
				/></template>
			</DataTable>
		</SectionCard>

		<SectionCard title="Empty state, loading and error">
			<div class="space-y-4">
				<EmptyState
					title="Nothing here yet"
					text="Add the first one with the button above."
					icon="lucide-inbox"
				>
					<AppButton variant="primary">Add</AppButton>
				</EmptyState>
				<LoadingSkeleton :rows="3" label="Loading." />
				<LoadError message="The list could not be loaded." />
			</div>
		</SectionCard>

		<SectionCard title="Record header">
			<RecordHeader
				title="Asha Rao"
				line="LD-0042, Powai, assigned to Gate Agent"
				:back-to="{ path: '/gallery' }"
				back-label="Back to the gallery"
			>
				<template #status><StatusBadge tone="info" label="Site visit booked" /></template>
				<template #actions>
					<AppButton>Archive</AppButton>
					<AppButton variant="primary">Edit</AppButton>
				</template>
			</RecordHeader>
		</SectionCard>

		<SectionCard title="Dialog and toast">
			<div class="flex flex-wrap items-center gap-2">
				<AppButton data-testid="sellos-gallery-dialog-open" @click="dialog = true"
					>Open a dialog</AppButton
				>
				<AppButton
					data-testid="sellos-gallery-toast"
					@click="showToast('Saved', { tone: 'success' })"
				>
					Show a toast
				</AppButton>
				<AppButton @click="showToast('It could not be saved', { tone: 'danger' })"
					>Show an error toast</AppButton
				>
			</div>
			<Dialog v-model="dialog" :options="{ title: 'Delete this lead?', size: 'md' }">
				<template #body-content>
					<p class="ui-text-secondary">
						A dialog has a title, one line, content and a footer.
					</p>
				</template>
				<template #actions>
					<AppButton @click="dialog = false">Cancel</AppButton>
					<AppButton variant="danger" confirm @click="dialog = false">Delete</AppButton>
				</template>
			</Dialog>
		</SectionCard>

		<template #footer>
			<FormFooter
				:dirty="dirty"
				save-label="Save"
				@save="dirty = false"
				@undo="dirty = false"
			/>
		</template>
	</PageTemplate>
</template>

<script setup>
// The gallery (docs/DESIGN_SYSTEM.md, section 2): every shared piece in every state, in each area's colours and a
// chosen brand colour. It is open to every signed in role and is not in the menu: /sellos/gallery.
import { Dialog } from "frappe-ui";
import { computed, onBeforeUnmount, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import EmptyState from "../components/EmptyState.vue";
import FieldGrid from "../components/FieldGrid.vue";
import FormField from "../components/FormField.vue";
import FormFooter from "../components/FormFooter.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import MoneyField from "../components/MoneyField.vue";
import Notice from "../components/Notice.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTabs from "../components/PageTabs.vue";
import PageTemplate from "../components/PageTemplate.vue";
import ReadField from "../components/ReadField.vue";
import RecordHeader from "../components/RecordHeader.vue";
import SectionCard from "../components/SectionCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { areas } from "../areas";
import { formatMoney, formatWhen } from "../format";
import { showToast } from "../shell";

const area = ref("sales");
const areaOptions = Object.entries(areas).map(([value, a]) => ({ value, label: a.label }));
const brand = ref("");
const text = ref("");
const choice = ref("One");
const money = ref("");
const agreed = ref(false);
const tab = ref("one");
const tabs = [
	{ key: "one", label: "First" },
	{ key: "two", label: "Second", count: 3 },
	{ key: "three", label: "Third" },
];
const dialog = ref(false);
const dirty = ref(true);

const tiles = computed(() => [
	{
		label: "Normal",
		value: 12,
		caption: "the area's colour",
		icon: areas[area.value].icon,
		to: "/",
	},
	{ label: "Waiting", value: 4, caption: "at risk", icon: "lucide-hourglass", tone: "warning" },
	{
		label: "Late",
		value: 2,
		caption: "past their date",
		icon: "lucide-clock-alert",
		tone: "danger",
	},
	{
		label: "Done",
		value: 30,
		caption: "this month",
		icon: "lucide-circle-check",
		tone: "success",
	},
]);
const columns = [
	{ key: "title", label: "Title", primary: true, sortable: true },
	{ key: "status", label: "Status" },
	{ key: "when", label: "When", sortable: true },
];
const rows = [
	{
		name: "a",
		title: "Asha Rao",
		status: "Done",
		tone: "success",
		when: formatWhen("2026-11-24 11:44:00"),
	},
	{
		name: "b",
		title: "Vikram Shah",
		status: "Waiting",
		tone: "warning",
		when: formatWhen("2026-11-23 16:10:00"),
	},
	{
		name: "c",
		title: "Meera Iyer",
		status: "Late",
		tone: "danger",
		when: formatWhen("2026-11-20 09:00:00"),
	},
];

function applyBrand(value) {
	const root = document.documentElement;
	if (/^#[0-9a-fA-F]{6}$/.test(value)) root.style.setProperty("--sos-brand", value);
}
function reset() {
	brand.value = "";
	document.documentElement.style.removeProperty("--sos-brand");
}
onBeforeUnmount(reset);
</script>
