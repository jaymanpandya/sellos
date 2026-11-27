<template>
	<PageTemplate data-testid="sellos-buildings-page">
		<template #header>
			<PageHeader
				title="Buildings"
				text="Buildings the system built wait here for a person to check them. Only a confirmed building is used for matching and market data."
				icon="lucide-building-2"
			>
				<AppButton
					v-if="isAdmin"
					type="button"
					data-testid="sellos-buildings-load"
					@click="openLoad"
				>
					Load a list
				</AppButton>
				<AppButton
					v-if="isAdmin"
					type="button"
					variant="primary"
					data-testid="sellos-buildings-new"
					@click="openBuilding(null)"
				>
					Add building
				</AppButton>
			</PageHeader>
		</template>

		<template #kpis>
			<KpiStrip :items="kpis" data-testid="sellos-buildings-stats" />
		</template>

		<template #filters>
			<FilterBar
				v-model:search="search"
				search-label="Search buildings"
				search-placeholder="Name, CTS or RERA number"
				search-testid="sellos-buildings-search"
				:active="Boolean(search)"
				data-testid="sellos-buildings-filters"
				@clear="search = ''"
			/>
		</template>

		<LoadError
			v-if="error && !editing && !loadingList"
			class="mb-ui-md"
			data-testid="sellos-buildings-error"
			:message="error"
			@retry="load"
		/>
		<Notice v-if="notice" class="mb-ui-md" testid="sellos-buildings-notice">
			{{ notice }}
		</Notice>

		<PageTabs v-model="tab" :tabs="tabs" label="Buildings" />

		<DataTable
			:title="tabTitle"
			caption="Buildings"
			:columns="columns"
			:rows="rows"
			:loading="loading"
			loading-label="Loading buildings."
			empty-title="No buildings here."
			:empty-text="emptyText"
			empty-icon="lucide-building-2"
			:row-clickable="canReview"
			testid="sellos-buildings-table"
			row-testid="sellos-building-row"
			:row-attrs="(row) => ({ 'data-status': row.status })"
			@row-click="openBuilding"
		>
			<template #cell-building_name="{ row }">
				<NameCell :name="row.building_name" :detail="row.project || ''" />
			</template>
			<template #cell-cts="{ row }">
				<CellText :value="row.cts_numbers.join(', ')" />
			</template>
			<template #cell-rera_number="{ row }">
				<CellText :value="row.rera_number" />
			</template>
			<template #cell-micro_market="{ row }">
				<CellText :value="marketName(row.micro_market)" />
			</template>
			<template #cell-status="{ row }">
				<StatusBadge
					:tone="row.status === 'Confirmed' ? 'success' : 'warning'"
					:label="row.status"
					data-testid="sellos-building-status"
				/>
			</template>
		</DataTable>

		<DataTable
			v-if="isAdmin"
			class="mt-ui-lg"
			title="Micro markets"
			caption="Micro markets"
			:columns="marketColumns"
			:rows="markets"
			empty-title="No micro markets yet."
			empty-text="Add one, or load a file of micro markets."
			empty-icon="lucide-map"
			row-clickable
			testid="sellos-markets-table"
			row-testid="sellos-market-row"
			@row-click="openMarket"
		>
			<template #cell-market_name="{ row }">
				<NameCell :name="row.market_name" :detail="row.parent_area" />
			</template>
		</DataTable>
		<div v-if="isAdmin" class="mt-ui-md flex flex-wrap gap-ui-sm">
			<AppButton type="button" data-testid="sellos-market-new" @click="openMarket(null)">
				Add micro market
			</AppButton>
		</div>

		<FormDrawer
			:open="editing"
			:title="form.name ? 'Check building' : 'Add building'"
			:text="
				form.name
					? 'Correct any field, then confirm the building. Every correction is kept with who made it and the old value.'
					: 'A building added by hand waits for review like any other.'
			"
			:submit-label="form.name ? 'Save corrections' : 'Add building'"
			:busy="saving"
			testid="sellos-building-form"
			submit-testid="sellos-building-save"
			@close="closeBuilding"
			@submit="saveBuilding"
		>
			<FormSection title="Building">
				<FormField
					v-model="form.building_name"
					label="Building"
					required
					class="md:col-span-2"
					data-testid="sellos-building-name"
				/>
				<FormField
					v-model="form.micro_market"
					type="select"
					label="Micro market"
					:options="marketOptions"
					data-testid="sellos-building-market"
				/>
				<FormField
					v-model="form.country"
					label="Country"
					data-testid="sellos-building-country"
				/>
			</FormSection>
			<FormSection title="Identifiers">
				<FormField
					v-for="field in shownFields"
					:key="field"
					v-model="form[field]"
					:label="identifierLabels[field]"
					:hint="field === 'cts_numbers' ? 'Separate several with a comma.' : ''"
					:data-testid="`sellos-building-${field.replace(/_/g, '-')}`"
				/>
			</FormSection>
			<FormSection v-if="form.name && corrections.length" title="Corrections">
				<ul class="space-y-1 md:col-span-2" data-testid="sellos-building-corrections">
					<li
						v-for="(c, i) in corrections"
						:key="i"
						class="ui-text-secondary"
						data-testid="sellos-building-correction"
					>
						{{ labelFor(c.fieldname) }}: was "{{ c.old_value || "empty" }}", now "{{
							c.new_value || "empty"
						}}" by {{ c.corrected_by }}
					</li>
				</ul>
			</FormSection>
			<p v-if="error" role="alert" class="ui-text-error" data-testid="sellos-building-error">
				{{ error }}
			</p>
			<template v-if="form.name && form.status !== 'Confirmed'" #footer-start>
				<AppButton
					type="button"
					variant="primary"
					:disabled="saving"
					data-testid="sellos-building-confirm"
					@click="confirm"
				>
					Confirm building
				</AppButton>
			</template>
		</FormDrawer>

		<FormDrawer
			:open="loadingList"
			title="Load a list of buildings"
			text="Paste one building or project name a line, or a CSV with a header (name, RERA number, CTS, village, tahsil, district, micro market). Each becomes a building that needs review."
			submit-label="Load list"
			:busy="saving"
			testid="sellos-seed-form"
			submit-testid="sellos-seed-save"
			@close="loadingList = false"
			@submit="loadList"
		>
			<FormSection title="List">
				<FormField
					v-model="seed.text"
					type="textarea"
					label="Buildings"
					required
					class="md:col-span-2"
					data-testid="sellos-seed-text"
				/>
				<FormField
					v-model="seed.micro_market"
					type="select"
					label="Micro market"
					:options="marketOptions"
					data-testid="sellos-seed-market"
				/>
			</FormSection>
			<p v-if="error" role="alert" class="ui-text-error" data-testid="sellos-seed-error">
				{{ error }}
			</p>
		</FormDrawer>

		<FormDrawer
			:open="marketOpen"
			:title="market.name ? 'Edit micro market' : 'Add micro market'"
			text="A micro market groups a company's buildings. Renaming keeps its history."
			:submit-label="market.name ? 'Save micro market' : 'Add micro market'"
			:busy="saving"
			testid="sellos-market-form"
			submit-testid="sellos-market-save"
			@close="marketOpen = false"
			@submit="saveMarket"
		>
			<FormSection title="Micro market">
				<FormField
					v-model="market.market_name"
					label="Micro market"
					required
					data-testid="sellos-market-name"
				/>
				<FormField
					v-model="market.country"
					label="Country"
					required
					data-testid="sellos-market-country"
				/>
				<FormField
					v-model="market.parent_area"
					label="City or region"
					required
					data-testid="sellos-market-city"
				/>
				<FormField
					v-model="market.boundary"
					type="textarea"
					label="Boundary (GeoJSON)"
					hint="Optional."
					class="md:col-span-2"
					data-testid="sellos-market-boundary"
				/>
			</FormSection>
			<p v-if="error" role="alert" class="ui-text-error" data-testid="sellos-market-error">
				{{ error }}
			</p>
			<template v-if="market.name" #footer-start>
				<AppButton
					type="button"
					:disabled="saving"
					data-testid="sellos-market-archive"
					@click="archiveMarket"
				>
					Archive
				</AppButton>
			</template>
		</FormDrawer>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";

import AppButton from "../components/AppButton.vue";
import CellText from "../components/CellText.vue";
import DataTable from "../components/DataTable.vue";
import FilterBar from "../components/FilterBar.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import KpiStrip from "../components/KpiStrip.vue";
import LoadError from "../components/LoadError.vue";
import NameCell from "../components/NameCell.vue";
import Notice from "../components/Notice.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTabs from "../components/PageTabs.vue";
import PageTemplate from "../components/PageTemplate.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { buildingsApi } from "../intel/buildingsApi";
import { session } from "../session";

// The building review (SOS-P3-04). The system builds buildings (a seed list, a file) as "Needs review". A
// Company Admin or Agent corrects each field and confirms the building; only a confirmed building is used by
// matching and market data. A Company Admin also adds buildings and keeps the micro markets. Every change is
// saved on the server and the list read back.
const identifierLabels = {
	cts_numbers: "CTS numbers",
	village: "Village",
	tahsil: "Tahsil",
	district: "District",
	rera_number: "RERA number",
	uae_community: "Community",
	dld_number: "DLD number",
	au_lot: "Lot",
	au_plan: "Plan",
};
const identifiers = Object.keys(identifierLabels);

const isAdmin = computed(() => session.roles.includes("SellOS Company Admin"));
const canReview = computed(() => isAdmin.value || session.roles.includes("SellOS Agent"));

const tab = ref("Needs review");
const search = ref("");
const all = ref([]);
const markets = ref([]);
const profiles = ref({ default_country: "", countries: {} });
const loading = ref(true);
const error = ref("");
const notice = ref("");
const saving = ref(false);
const editing = ref(false);
const loadingList = ref(false);
const marketOpen = ref(false);
const corrections = ref([]);

const blankBuilding = () => ({
	name: "",
	status: "",
	building_name: "",
	micro_market: "",
	country: "",
	cts_numbers: "",
	village: "",
	tahsil: "",
	district: "",
	rera_number: "",
	uae_community: "",
	dld_number: "",
	au_lot: "",
	au_plan: "",
});
const form = reactive(blankBuilding());
const seed = reactive({ text: "", micro_market: "" });
const market = reactive({
	name: "",
	market_name: "",
	country: "",
	parent_area: "",
	boundary: "",
});

const rows = computed(() => {
	const text = search.value.trim().toLowerCase();
	return all.value
		.filter((b) => tab.value === "All" || b.status === tab.value)
		.filter(
			(b) =>
				!text ||
				b.building_name.toLowerCase().includes(text) ||
				b.rera_number.toLowerCase().includes(text) ||
				b.cts_numbers.some((c) => c.toLowerCase().includes(text))
		);
});
const count = (status) => all.value.filter((b) => b.status === status).length;
const tabs = computed(() => [
	{ key: "Needs review", label: "Needs review", count: count("Needs review") },
	{ key: "Confirmed", label: "Confirmed", count: count("Confirmed") },
	{ key: "All", label: "All", count: all.value.length },
]);
const tabTitle = computed(() => (tab.value === "All" ? "All buildings" : tab.value));
const emptyText = computed(() =>
	tab.value === "Needs review"
		? "Every building has been checked."
		: "Buildings appear here as they are added."
);
const kpis = computed(() => [
	{
		label: "Needs review",
		value: count("Needs review"),
		caption: "waiting for a person",
		icon: "lucide-clipboard-check",
		tone: count("Needs review") ? "warning" : undefined,
	},
	{
		label: "Confirmed",
		value: count("Confirmed"),
		caption: "used for matching and market data",
		icon: "lucide-circle-check",
		tone: "success",
	},
	{
		label: "Micro markets",
		value: markets.value.length,
		caption: "active",
		icon: "lucide-map",
	},
]);
const columns = [
	{ key: "building_name", label: "Building", primary: true, sortable: true },
	{
		key: "cts",
		label: "CTS",
		sortValue: (b) => b.cts_numbers.join(", "),
	},
	{ key: "rera_number", label: "RERA", sortable: true },
	{
		key: "micro_market",
		label: "Micro market",
		sortable: true,
		sortValue: (b) => marketName(b.micro_market),
	},
	{ key: "status", label: "Status", sortable: true },
];
const marketColumns = [
	{ key: "market_name", label: "Micro market", primary: true, sortable: true },
	{ key: "country", label: "Country", sortable: true },
	{ key: "buildings", label: "Buildings", sortable: true, align: "right" },
];

const marketName = (name) => markets.value.find((m) => m.name === name)?.market_name || name || "";
const marketOptions = computed(() => [
	{ label: "No micro market", value: "" },
	...markets.value.map((m) => ({ label: m.market_name, value: m.name })),
]);
// Which identifiers show follows the building's country.
const shownFields = computed(() => {
	const p = profiles.value;
	const own = p.countries[form.country] || p.countries[p.default_country] || identifiers;
	return identifiers.filter((f) => own.includes(f));
});
const labelFor = (fieldname) => identifierLabels[fieldname] || fieldname.replace(/_/g, " ");

async function load() {
	error.value = "";
	try {
		const [list, marketData] = await Promise.all([
			buildingsApi.list({ page_length: 200 }),
			buildingsApi.listMarkets(),
		]);
		all.value = list.rows;
		profiles.value = list.identifier_profiles;
		markets.value = marketData.markets;
	} catch (e) {
		error.value = serverMessage(e, "The buildings could not be loaded.");
	} finally {
		loading.value = false;
	}
}

async function openBuilding(row) {
	error.value = "";
	notice.value = "";
	Object.assign(form, blankBuilding());
	corrections.value = [];
	if (row) {
		Object.assign(form, row, { cts_numbers: row.cts_numbers.join(", ") });
		editing.value = true;
		try {
			corrections.value = (await buildingsApi.get(row.name)).corrections;
		} catch (e) {
			error.value = serverMessage(e, "The corrections could not be loaded.");
		}
	} else {
		form.country = profiles.value.default_country;
		editing.value = true;
	}
}
const closeBuilding = () => {
	editing.value = false;
};

const values = () => ({
	building_name: form.building_name,
	micro_market: form.micro_market,
	country: form.country,
	...Object.fromEntries(shownFields.value.map((f) => [f, form[f]])),
});

async function run(action, fallback) {
	saving.value = true;
	error.value = "";
	try {
		await action();
		return true;
	} catch (e) {
		error.value = serverMessage(e, fallback);
		return false;
	} finally {
		saving.value = false;
	}
}

async function saveBuilding() {
	if (!form.building_name.trim()) {
		error.value = "Enter the building's name.";
		return;
	}
	const done = await run(
		() =>
			form.name ? buildingsApi.correct(form.name, values()) : buildingsApi.save(values()),
		"The building could not be saved."
	);
	if (done) {
		editing.value = false;
		notice.value = form.name ? "Corrections saved." : "Building added.";
		await load();
	}
}

async function confirm() {
	const done = await run(
		() => buildingsApi.confirm(form.name),
		"The building could not be confirmed."
	);
	if (done) {
		editing.value = false;
		notice.value = "Building confirmed.";
		await load();
	}
}

function openLoad() {
	error.value = "";
	notice.value = "";
	Object.assign(seed, { text: "", micro_market: "" });
	loadingList.value = true;
}

async function loadList() {
	if (!seed.text.trim()) {
		error.value = "Paste at least one building or project name.";
		return;
	}
	let result;
	const done = await run(async () => {
		result = await buildingsApi.loadSeedList(seed.text, seed.micro_market || null);
	}, "The list could not be loaded.");
	if (done) {
		loadingList.value = false;
		notice.value = `${result.created} added, ${result.skipped} already there, ${result.rejected.length} not read.`;
		tab.value = "Needs review";
		await load();
	}
}

function openMarket(row) {
	error.value = "";
	Object.assign(
		market,
		row
			? { ...row, boundary: row.boundary || "" }
			: {
					name: "",
					market_name: "",
					country: profiles.value.default_country,
					parent_area: "",
					boundary: "",
			  }
	);
	marketOpen.value = true;
}

async function saveMarket() {
	if (!market.market_name.trim() || !market.country.trim() || !market.parent_area.trim()) {
		error.value = "Fill in the name, the country and the city or region.";
		return;
	}
	const done = await run(
		() =>
			buildingsApi.saveMarket(
				{
					market_name: market.market_name,
					country: market.country,
					parent_area: market.parent_area,
					boundary: market.boundary,
				},
				market.name || null
			),
		"The micro market could not be saved."
	);
	if (done) {
		marketOpen.value = false;
		await load();
	}
}

async function archiveMarket() {
	const done = await run(
		() => buildingsApi.archiveMarket(market.name),
		"The micro market could not be archived."
	);
	if (done) {
		marketOpen.value = false;
		await load();
	}
}

watch(tab, () => {
	notice.value = "";
});
onMounted(load);
</script>
