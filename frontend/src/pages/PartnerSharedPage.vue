<template>
	<div data-testid="sellos-partner-shared-page">
		<PageHeader
			title="Shared projects"
			text="The projects, units, prices and brochures the company has shared with your firm."
			icon="lucide-building-2"
		/>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-partner-shared-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<ListCard title="Projects">
			<EmptyState
				v-if="loaded && !loadError && !projects.length"
				title="Nothing is shared with your firm yet"
				text="The company will share projects with you here."
				icon="lucide-building-2"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-partner-shared-list">
				<li
					v-for="p in projects"
					:key="p.name"
					data-testid="sellos-partner-shared-row"
					:data-name="p.name"
					class="flex flex-wrap items-center gap-3 rounded-input border border-line-soft p-ui-md"
				>
					<span class="font-medium text-ink" data-testid="sellos-partner-shared-name">
						{{ p.project_name }}
					</span>
					<span class="text-sm text-ink-muted">
						{{ p.locality }} {{ p.city }}: {{ p.units }} units
					</span>
					<AppButton
						type="button"
						data-testid="sellos-partner-shared-open"
						@click="open(p.name)"
					>
						Open
					</AppButton>
				</li>
			</ul>
		</ListCard>

		<ListCard v-if="detail" :title="detail.project.project_name" class="mt-ui-md">
			<div data-testid="sellos-partner-shared-detail" :data-project="detail.project.name">
				<p class="text-sm text-ink-muted">
					RERA {{ detail.project.rera_number }}, {{ detail.project.project_status }},
					{{ detail.project.locality }} {{ detail.project.city }}
				</p>
				<h3 class="mt-ui-md font-medium text-ink">Units</h3>
				<ul class="space-y-1 text-sm" data-testid="sellos-partner-shared-units">
					<li
						v-for="u in detail.units"
						:key="u.name"
						data-testid="sellos-partner-shared-unit"
					>
						{{ u.tower }} {{ u.unit_number }}, {{ u.configuration }},
						{{ u.carpet_area }} sq ft, floor {{ u.floor }}: {{ u.status }}
					</li>
				</ul>
				<template v-if="detail.price_list">
					<h3 class="mt-ui-md font-medium text-ink">Price list</h3>
					<p class="text-sm" data-testid="sellos-partner-shared-price">
						{{ detail.price_list.title }}: Rs {{ detail.price_list.base_rate }} per sq
						ft, floor rise Rs {{ detail.price_list.floor_rise_rate }} per sq ft above
						floor
						{{ detail.price_list.floor_rise_from_floor }}
					</p>
					<ul class="text-sm text-ink-muted">
						<li v-for="c in detail.price_list.charges" :key="c.charge_name">
							{{ c.charge_name }}: {{ c.value }} ({{ c.basis }})
						</li>
					</ul>
				</template>
				<template v-if="detail.brochures.length">
					<h3 class="mt-ui-md font-medium text-ink">Brochures</h3>
					<ul class="text-sm">
						<li v-for="b in detail.brochures" :key="b.name">
							<a
								:href="b.file_url"
								target="_blank"
								rel="noopener"
								class="text-accent underline"
								data-testid="sellos-partner-shared-brochure"
							>
								{{ b.title }}
							</a>
						</li>
					</ul>
				</template>
			</div>
		</ListCard>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import { partnerSharesApi } from "../company/partnerSharesApi";
import { serverMessage } from "../crm/crmApi";

// What the company shares with the signed in partner's firm (SOS-P7-03). Read only: the server decides what
// is shown, at the moment of each call.
const projects = ref([]);
const detail = ref(null);
const loadError = ref("");
const loaded = ref(false);

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
