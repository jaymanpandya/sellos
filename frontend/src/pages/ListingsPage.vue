<template>
	<div data-testid="sellos-listings-page">
		<PageHeader
			title="Listings"
			text="A listing offers a unit or a property as Primary, Direct or Partner. The website shows it only once it is published."
			icon="lucide-megaphone"
		/>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-listing-error"
			class="mb-ui-md text-sm text-accent"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-listing-notice"
			class="mb-ui-md text-sm text-ink"
		>
			{{ notice }}
		</p>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-listing-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<ListCard title="Listings">
			<EmptyState
				v-if="loaded && !loadError && !listings.length"
				title="No listings yet"
				text="Make the first listing below."
				icon="lucide-megaphone"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-listing-list">
				<li
					v-for="l in listings"
					:key="l.name"
					data-testid="sellos-listing-row"
					:data-name="l.name"
					:data-title="l.title"
					:data-published="l.published"
					class="rounded-input border border-line-soft p-ui-md"
				>
					<div class="flex flex-wrap items-center gap-3">
						<span class="font-medium text-ink">{{ l.title }}</span>
						<StatusBadge
							tone="info"
							:label="l.listing_type"
							data-testid="sellos-listing-type"
						/>
						<StatusBadge
							:tone="l.published ? 'success' : 'neutral'"
							:label="l.published ? 'Published' : 'Draft'"
							data-testid="sellos-listing-state"
						/>
						<span class="text-sm text-ink-muted" data-testid="sellos-listing-price">
							{{ l.asking_price ? rupees(l.asking_price) : "No price yet" }}
						</span>
					</div>
					<p class="text-sm text-ink-muted" data-testid="sellos-listing-target">
						{{ l.target_label || "Nothing chosen to offer yet" }}
					</p>
					<p
						v-if="!l.published && l.missing.length"
						class="text-sm text-ink-muted"
						data-testid="sellos-listing-missing"
					>
						Needs {{ l.missing.join(", ") }} before it can be published.
					</p>
					<div v-if="canEdit" class="mt-ui-sm flex flex-wrap gap-ui-sm">
						<AppButton
							v-if="!l.published"
							type="button"
							variant="primary"
							data-testid="sellos-listing-publish"
							@click="
								act(() => listingApi.publish(l.name), `${l.title} is published.`)
							"
						>
							Publish
						</AppButton>
						<AppButton
							v-else
							type="button"
							data-testid="sellos-listing-unpublish"
							@click="
								act(() => listingApi.unpublish(l.name), `${l.title} is withdrawn.`)
							"
						>
							Withdraw
						</AppButton>
						<AppButton
							type="button"
							data-testid="sellos-listing-edit"
							@click="edit(l)"
						>
							Edit
						</AppButton>
						<AppButton
							v-if="canArchive"
							type="button"
							data-testid="sellos-listing-archive"
							@click="
								act(
									() => listingApi.setArchived(l.name, 1),
									`${l.title} is archived.`
								)
							"
						>
							Archive
						</AppButton>
					</div>
					<details class="mt-ui-sm" data-testid="sellos-listing-history">
						<summary class="cursor-pointer text-sm text-ink-muted">
							Change history
						</summary>
						<ul class="mt-1 space-y-1 text-sm text-ink-muted">
							<li
								v-for="(c, i) in l.changes"
								:key="i"
								data-testid="sellos-listing-change"
							>
								{{ c.changed_on }}: {{ c.changed_by_name }} set
								{{ c.what.toLowerCase() }}
								<span v-if="c.old">from {{ c.old }}</span> to {{ c.new }}
							</li>
						</ul>
					</details>
				</li>
			</ul>
		</ListCard>

		<form
			v-if="canEdit"
			class="ui-card mt-ui-md"
			data-testid="sellos-listing-form"
			@submit.prevent="save"
		>
			<h2 class="ui-card-heading mb-ui-md">
				{{ editing ? "Edit the listing" : "Make a listing" }}
			</h2>
			<div class="grid grid-cols-1 gap-x-ui-md gap-y-ui-md md:grid-cols-2">
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
					data-testid="sellos-listing-target-field"
				/>
				<MoneyField
					v-model="form.asking_price"
					label="Asking price (Rs)"
					data-testid="sellos-listing-price-field"
				/>
				<FormField
					v-model="form.description"
					label="Description"
					data-testid="sellos-listing-description"
				/>
			</div>
			<div class="mt-ui-md flex flex-wrap gap-ui-sm">
				<AppButton type="submit" variant="primary" data-testid="sellos-listing-save">
					Save listing
				</AppButton>
				<AppButton
					v-if="editing"
					type="button"
					data-testid="sellos-listing-cancel"
					@click="reset"
				>
					Cancel
				</AppButton>
			</div>
		</form>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import MoneyField from "../components/MoneyField.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { listingApi, rupees } from "../inventory/inventoryApi";

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
	try {
		show(await action());
		notice.value = message;
		return true;
	} catch (e) {
		error.value = serverMessage(e, "The change could not be saved.");
		return false;
	}
}

function reset() {
	editing.value = "";
	current.value = null;
	Object.assign(form, blank());
}

function edit(l) {
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
