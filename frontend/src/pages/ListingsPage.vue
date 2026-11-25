<template>
	<PageTemplate shape="list" data-testid="sellos-listings-page">
		<template #header>
			<PageHeader
				title="Listings"
				text="A listing offers a unit or a property as Primary, Direct or Partner. The website shows it only once it is published."
				icon="lucide-megaphone"
			>
				<AppButton
					v-if="canEdit"
					type="button"
					variant="primary"
					data-testid="sellos-listing-new"
					@click="startNew"
				>
					<template #prefix
						><span class="lucide-plus icon-inherit size-4" aria-hidden="true"
					/></template>
					Make a listing
				</AppButton>
			</PageHeader>
		</template>

		<template v-if="loaded && !loadError" #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-listings-stats" />
		</template>

		<p
			v-if="error"
			role="alert"
			data-testid="sellos-listing-error"
			class="mb-ui-md ui-text-error"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-listing-notice"
			class="mb-ui-md ui-text-small"
		>
			{{ notice }}
		</p>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-listing-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<DataTable
			v-if="!loadError"
			title="Listings"
			caption="Listings"
			:columns="columns"
			:rows="listings"
			:loading="!loaded"
			loading-label="Loading listings."
			:row-attrs="
				(l) => ({
					'data-title': l.title,
					'data-published': l.published,
				})
			"
			:row-name="(l) => l.title"
			empty-title="No listings yet"
			empty-text="Make the first listing."
			empty-icon="lucide-megaphone"
			testid="sellos-listing-list"
			row-testid="sellos-listing-row"
		>
			<template #cell-title="{ row }">
				<span class="ui-text-strong">{{ row.title }}</span>
			</template>
			<template #cell-listing_type="{ row }">
				<StatusBadge
					tone="info"
					:label="row.listing_type"
					data-testid="sellos-listing-type"
				/>
			</template>
			<template #cell-published="{ row }">
				<StatusBadge
					:tone="row.published ? 'success' : 'neutral'"
					:label="row.published ? 'Published' : 'Draft'"
					data-testid="sellos-listing-state"
				/>
			</template>
			<template #cell-asking_price="{ row }">
				<span data-testid="sellos-listing-price">
					{{ row.asking_price ? formatMoney(row.asking_price) : "No price yet" }}
				</span>
			</template>
			<template #cell-target="{ row }">
				<p data-testid="sellos-listing-target">
					{{ row.target_label || "Nothing chosen to offer yet" }}
				</p>
				<p
					v-if="!row.published && row.missing.length"
					class="ui-text-muted"
					data-testid="sellos-listing-missing"
				>
					Needs {{ row.missing.join(", ") }} before it can be published.
				</p>
			</template>
			<template #cell-actions="{ row }">
				<div class="flex flex-wrap gap-ui-sm">
					<AppButton
						type="button"
						:active="shownMedia.has(row.name)"
						data-testid="sellos-listing-media-toggle"
						@click="toggleMedia(row.name)"
					>
						Photos and videos ({{ row.media_count }})
					</AppButton>
					<template v-if="canEdit">
						<AppButton
							v-if="!row.published"
							type="button"
							variant="primary"
							data-testid="sellos-listing-publish"
							@click="
								act(
									() => listingApi.publish(row.name),
									`${row.title} is published.`
								)
							"
						>
							Publish
						</AppButton>
						<AppButton
							v-else
							type="button"
							data-testid="sellos-listing-unpublish"
							@click="
								act(
									() => listingApi.unpublish(row.name),
									`${row.title} is withdrawn.`
								)
							"
						>
							Withdraw
						</AppButton>
						<AppButton
							type="button"
							data-testid="sellos-listing-edit"
							@click="edit(row)"
						>
							Edit
						</AppButton>
						<AppButton
							v-if="canArchive"
							type="button"
							data-testid="sellos-listing-archive"
							@click="
								act(
									() => listingApi.setArchived(row.name, 1),
									`${row.title} is archived.`
								)
							"
						>
							Archive
						</AppButton>
					</template>
				</div>
				<SuitedLeads v-if="row.published" kind="listing" :name="row.name" />
				<details class="mt-ui-sm" data-testid="sellos-listing-history">
					<summary class="cursor-pointer ui-text-muted">Change history</summary>
					<ul class="mt-1 space-y-1 ui-text-muted">
						<li
							v-for="(c, i) in row.changes"
							:key="i"
							data-testid="sellos-listing-change"
						>
							{{ formatWhen(c.changed_on) }}: {{ c.changed_by_name }} set
							{{ c.what.toLowerCase() }}
							<span v-if="c.old">from {{ c.old }}</span> to {{ c.new }}
						</li>
					</ul>
				</details>
			</template>
		</DataTable>

		<!-- The photos and videos of a listing open under the table, full width, not inside a narrow cell. -->
		<ListCard
			v-for="name in [...shownMedia]"
			:key="name"
			:title="`Photos and videos: ${listingTitle(name)}`"
			class="mt-ui-md"
			data-testid="sellos-listing-media-panel"
		>
			<ListingMedia :listing="name" @changed="load" />
		</ListCard>

		<FormDrawer
			v-if="canEdit"
			:open="formOpen"
			:title="editing ? 'Edit the listing' : 'Make a listing'"
			submit-label="Save listing"
			:busy="saving"
			testid="sellos-listing-form"
			submit-testid="sellos-listing-save"
			cancel-testid="sellos-listing-cancel"
			@close="reset"
			@submit="save"
		>
			<FormSection title="Listing">
				<FormField
					v-model="form.title"
					label="Title"
					required
					data-testid="sellos-listing-title"
				/>
				<FormField
					v-model="form.listing_type"
					type="select"
					label="Type"
					required
					:options="listingTypes"
					data-testid="sellos-listing-type-field"
				/>
				<FormField
					v-model="form.target"
					type="select"
					label="What is offered"
					:options="targetOptions"
					hint="A Primary listing offers a unit. Direct and Partner listings offer a unit or a property."
					class="md:col-span-2"
					data-testid="sellos-listing-target-field"
				/>
			</FormSection>
			<FormSection title="Price and description">
				<MoneyField
					v-model="form.asking_price"
					label="Asking price (Rs)"
					data-testid="sellos-listing-price-field"
				/>
				<FormField
					v-model="form.description"
					label="Description"
					class="md:col-span-2"
					data-testid="sellos-listing-description"
				/>
			</FormSection>
		</FormDrawer>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import MoneyField from "../components/MoneyField.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { formatMoney, formatWhen } from "../format";
import ListCard from "../components/ListCard.vue";
import ListingMedia from "../inventory/ListingMedia.vue";
import SuitedLeads from "../inventory/SuitedLeads.vue";
import { listingApi } from "../inventory/inventoryApi";

// Listings (SOS-P4-02). Every change is made on the server and the list read back, so what is shown is what
// is saved. Publishing is the server's decision: it names what a listing still needs.
const listings = ref([]);
const units = ref([]);
const properties = ref([]);
const listingTypes = ref([]);
const canEdit = ref(false);
const canArchive = ref(false);
const error = ref("");
const notice = ref("");
const loadError = ref("");
const loaded = ref(false);
const editing = ref("");
const formOpen = ref(false);
const saving = ref(false);

const kpis = computed(() => {
	const published = listings.value.filter((l) => l.published).length;
	return [
		{
			label: "Listings",
			value: listings.value.length,
			caption: "all listings",
			icon: "lucide-megaphone",
		},
		{
			label: "Published",
			value: published,
			caption: "shown on the website",
			icon: "lucide-globe",
			tone: "success",
		},
		{
			label: "Drafts",
			value: listings.value.length - published,
			caption: "not yet published",
			icon: "lucide-file-pen",
		},
	];
});
const columns = [
	{ key: "title", label: "Listing", primary: true, sortable: true },
	{ key: "listing_type", label: "Type", sortable: true },
	{ key: "published", label: "State", sortable: true, sortValue: (l) => (l.published ? 1 : 0) },
	{
		key: "asking_price",
		label: "Asking price",
		align: "right",
		sortable: true,
		sortValue: (l) => Number(l.asking_price || 0),
	},
	{ key: "target", label: "Offers", wrap: true, class: "min-w-[12rem]" },
	{ key: "actions", label: "Actions", wrap: true, class: "min-w-[16rem]" },
];
function startNew() {
	error.value = "";
	reset();
	formOpen.value = true;
}
// The listings whose photos and videos are open (SOS-P4-03).
const shownMedia = ref(new Set());
const listingTitle = (name) => listings.value.find((l) => l.name === name)?.title || name;
function toggleMedia(name) {
	const next = new Set(shownMedia.value);
	if (!next.delete(name)) next.add(name);
	shownMedia.value = next;
}

const NONE = "";
const blank = () => ({
	title: "",
	listing_type: "Direct",
	target: NONE,
	asking_price: "",
	description: "",
});
const form = reactive(blank());
// What the listing being edited already offers, kept in the box even when it is no longer offerable.
const current = ref(null);

// "Unit|UNIT-0001" or "Property|PROP-00001", so one box picks either.
const targetOptions = computed(() => [
	{ label: "Nothing yet (a draft)", value: NONE },
	...(current.value &&
	![
		...units.value.map((u) => `Unit|${u.value}`),
		...properties.value.map((p) => `Property|${p.value}`),
	].includes(current.value.value)
		? [current.value]
		: []),
	...units.value.map((u) => ({ label: `Unit: ${u.label}`, value: `Unit|${u.value}` })),
	...(form.listing_type === "Primary"
		? []
		: properties.value.map((p) => ({
				label: `Property: ${p.label}`,
				value: `Property|${p.value}`,
		  }))),
]);

function show(data) {
	listings.value = data.listings;
	units.value = data.units;
	properties.value = data.properties;
	listingTypes.value = data.listing_types;
	canEdit.value = data.can_edit;
	canArchive.value = data.can_archive;
}

async function load() {
	loadError.value = "";
	try {
		show(await listingApi.overview());
	} catch (e) {
		loadError.value = serverMessage(e, "The listings could not be loaded.");
	} finally {
		loaded.value = true;
	}
}

async function act(action, message) {
	error.value = "";
	notice.value = "";
	saving.value = true;
	try {
		show(await action());
		notice.value = message;
		return true;
	} catch (e) {
		error.value = serverMessage(e, "The change could not be saved.");
		return false;
	} finally {
		saving.value = false;
	}
}

function reset() {
	formOpen.value = false;
	editing.value = "";
	current.value = null;
	Object.assign(form, blank());
}

function edit(l) {
	error.value = "";
	formOpen.value = true;
	editing.value = l.name;
	const value = l.unit ? `Unit|${l.unit}` : l.property ? `Property|${l.property}` : NONE;
	current.value = value ? { label: l.target_label, value } : null;
	Object.assign(form, {
		title: l.title,
		listing_type: l.listing_type,
		target: l.unit ? `Unit|${l.unit}` : l.property ? `Property|${l.property}` : NONE,
		asking_price: l.asking_price || "",
		description: l.description,
	});
}

async function save() {
	const [kind, target] = form.target ? form.target.split("|") : [NONE, NONE];
	const values = {
		title: form.title,
		listing_type: form.listing_type,
		unit: kind === "Unit" ? target : "",
		property: kind === "Property" ? target : "",
		asking_price: form.asking_price === "" ? 0 : form.asking_price,
		description: form.description,
	};
	const title = form.title;
	if (
		await act(() => listingApi.save(values, editing.value || undefined), `${title} is saved.`)
	) {
		reset();
	}
}

onMounted(load);
</script>
