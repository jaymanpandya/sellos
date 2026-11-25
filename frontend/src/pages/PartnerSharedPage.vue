<template>
	<PageTemplate data-testid="sellos-partner-shared-page">
		<template #header>
			<PageHeader
				title="Shared projects"
				text="The projects, units, prices and brochures the company has shared with your firm."
				icon="lucide-building-2"
			/>
		</template>

		<template v-if="!loadError && loaded" #kpis>
			<KpiStrip
				:items="[
					{
						label: 'Shared projects',
						value: projects.length,
						caption: 'Shared with your firm',
						icon: 'lucide-building-2',
					},
					{
						label: 'Units',
						value: totalUnits,
						caption: 'Across the shared projects',
						icon: 'lucide-layers',
					},
				]"
				data-testid="sellos-partner-shared-stats"
			/>
		</template>

		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-partner-shared-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<div class="space-y-ui-md">
			<DataTable
				title="Projects"
				:columns="columns"
				:rows="projects"
				:loading="!loaded"
				empty-title="Nothing is shared with your firm yet"
				empty-text="The company will share projects with you here."
				empty-icon="lucide-building-2"
				testid="sellos-partner-shared-list"
				row-testid="sellos-partner-shared-row"
				empty-testid="sellos-partner-shared-empty"
			>
				<template #cell-project_name="{ row: p }">
					<span class="ui-text-strong" data-testid="sellos-partner-shared-name">
						{{ p.project_name }}
					</span>
				</template>
				<template #cell-place="{ row: p }">{{ p.locality }} {{ p.city }}</template>
				<template #cell-open="{ row: p }">
					<AppButton
						type="button"
						data-testid="sellos-partner-shared-open"
						@click="open(p.name)"
					>
						Open
					</AppButton>
				</template>
			</DataTable>

			<template v-if="detail">
				<ListCard :title="detail.project.project_name">
					<div
						data-testid="sellos-partner-shared-detail"
						:data-project="detail.project.name"
					>
						<p class="ui-text-muted">
							RERA {{ detail.project.rera_number }},
							{{ detail.project.project_status }}, {{ detail.project.locality }}
							{{ detail.project.city }}
						</p>
						<template v-if="detail.price_list">
							<p class="mt-ui-md ui-text-strong">Price list</p>
							<p class="mt-ui-sm" data-testid="sellos-partner-shared-price">
								{{ detail.price_list.title }}: Rs
								{{ detail.price_list.base_rate }} per sq ft, floor rise Rs
								{{ detail.price_list.floor_rise_rate }} per sq ft above floor
								{{ detail.price_list.floor_rise_from_floor }}
							</p>
							<ul class="ui-text-muted">
								<li v-for="c in detail.price_list.charges" :key="c.charge_name">
									{{ c.charge_name }}: {{ c.value }} ({{ c.basis }})
								</li>
							</ul>
						</template>
						<template v-if="detail.brochures.length">
							<p class="mt-ui-md ui-text-strong">Brochures</p>
							<ul class="mt-ui-sm ui-text-small">
								<li v-for="b in detail.brochures" :key="b.name">
									<a
										:href="b.file_url"
										target="_blank"
										rel="noopener"
										class="underline ui-text-error"
										data-testid="sellos-partner-shared-brochure"
									>
										{{ b.title }}
									</a>
								</li>
							</ul>
						</template>
					</div>
				</ListCard>
				<DataTable
					title="Units"
					:columns="unitColumns"
					:rows="detail.units"
					empty-title="No units shared"
					testid="sellos-partner-shared-units"
					row-testid="sellos-partner-shared-unit"
					empty-testid="sellos-partner-shared-units-empty"
				>
					<template #cell-unit_number="{ row: u }"
						>{{ u.tower }} {{ u.unit_number }}</template
					>
					<template #cell-carpet_area="{ row: u }">{{ u.carpet_area }} sq ft</template>
				</DataTable>
			</template>
		</div>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import DataTable from "../components/DataTable.vue";
import KpiStrip from "../components/KpiStrip.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import { partnerSharesApi } from "../company/partnerSharesApi";
import { serverMessage } from "../crm/crmApi";

// What the company shares with the signed in partner's firm (SOS-P7-03). Read only: the server decides what
// is shown, at the moment of each call.
const projects = ref([]);
const detail = ref(null);
const loadError = ref("");
const loaded = ref(false);

const columns = [
	{ key: "project_name", label: "Project", primary: true, sortable: true },
	{ key: "place", label: "Place" },
	{ key: "units", label: "Units", align: "right", sortable: true },
	{ key: "open", label: "" },
];
const unitColumns = [
	{ key: "unit_number", label: "Unit", primary: true },
	{ key: "configuration", label: "Configuration" },
	{ key: "carpet_area", label: "Carpet area", align: "right" },
	{ key: "floor", label: "Floor", align: "right" },
	{ key: "status", label: "Status" },
];

const totalUnits = computed(() => projects.value.reduce((n, p) => n + Number(p.units || 0), 0));

async function load() {
	loadError.value = "";
	try {
		projects.value = (await partnerSharesApi.mine()).projects;
	} catch (e) {
		loadError.value = serverMessage(e, "The shared projects could not be loaded.");
	} finally {
		loaded.value = true;
	}
}

async function open(name) {
	try {
		detail.value = await partnerSharesApi.mineOne(name);
	} catch (e) {
		loadError.value = serverMessage(e, "That project could not be loaded.");
	}
}

onMounted(load);
</script>
