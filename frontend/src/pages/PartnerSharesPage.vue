<template>
	<div data-testid="sellos-shares-page">
		<PageHeader
			title="Share with partners"
			text="Choose what each channel partner firm may see: a project, all its units or chosen ones, its price list and brochures. A partner sees nothing else. A withdrawn share stops showing at once."
			icon="lucide-share-2"
		/>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-shares-error"
			class="mb-ui-md text-sm text-accent"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-shares-notice"
			class="mb-ui-md text-sm text-ink"
		>
			{{ notice }}
		</p>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-shares-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>

		<form class="ui-card mb-ui-md" data-testid="sellos-shares-form" @submit.prevent="share">
			<h2 class="ui-card-heading mb-ui-md">Share a project</h2>
			<FormField
				v-model="form.project"
				type="select"
				label="Project"
				:options="projectOptions"
				data-testid="sellos-shares-project"
				@update:model-value="chooseProject"
			/>

			<template v-if="form.project">
				<fieldset class="mt-ui-md" data-testid="sellos-shares-firms">
					<legend class="text-sm font-medium text-ink">Share with</legend>
					<AppCheckbox
						v-model="form.every"
						label="Every Approved firm"
						data-testid="sellos-shares-every"
					/>
					<template v-if="!form.every">
						<AppCheckbox
							v-for="f in options.firms"
							:key="f.name"
							v-model="form.firms[f.name]"
							:label="f.firm_name"
							:data-testid="`sellos-shares-firm-${f.name}`"
						/>
						<p v-if="!options.firms.length" class="text-sm text-ink-muted">
							No firm is Approved yet.
						</p>
					</template>
				</fieldset>

				<fieldset class="mt-ui-md" data-testid="sellos-shares-units">
					<legend class="text-sm font-medium text-ink">Units</legend>
					<AppCheckbox
						v-model="form.allUnits"
						label="All units of the project"
						data-testid="sellos-shares-all-units"
					/>
					<template v-if="!form.allUnits">
						<AppCheckbox
							v-for="u in options.units"
							:key="u.name"
							v-model="form.units[u.name]"
							:label="unitLabel(u)"
							:data-testid="`sellos-shares-unit-${u.name}`"
						/>
					</template>
				</fieldset>

				<fieldset class="mt-ui-md">
					<legend class="text-sm font-medium text-ink">Price list and brochures</legend>
					<AppCheckbox
						v-model="form.priceList"
						:label="
							options.price_list
								? `The price list in force (${options.price_list.title})`
								: 'The price list in force (this project has none yet)'
						"
						data-testid="sellos-shares-price-list"
					/>
					<AppCheckbox
						v-for="m in options.brochures"
						:key="m.name"
						v-model="form.brochures[m.name]"
						:label="`${m.title} (${m.media_type})`"
						:data-testid="`sellos-shares-brochure-${m.name}`"
					/>
				</fieldset>

				<div class="mt-ui-md">
					<AppButton type="submit" variant="primary" data-testid="sellos-shares-submit">
						Share
					</AppButton>
				</div>
			</template>
		</form>

		<ListCard title="Shares">
			<EmptyState
				v-if="loaded && !loadError && !shares.length"
				title="Nothing is shared yet"
				text="Share a project above."
				icon="lucide-share-2"
			/>
			<ul class="space-y-ui-sm" data-testid="sellos-shares-list">
				<li
					v-for="s in shares"
					:key="s.name"
					data-testid="sellos-shares-row"
					:data-name="s.name"
					:data-status="s.status"
					:data-project="s.project"
					class="rounded-input border border-line-soft p-ui-md"
				>
					<div class="flex flex-wrap items-center gap-3">
						<span class="font-medium text-ink" data-testid="sellos-shares-row-project">
							{{ s.project_name }}
						</span>
						<span class="text-sm text-ink-muted" data-testid="sellos-shares-row-firm">
							with {{ s.firm_name }}
						</span>
						<StatusBadge
							:tone="s.status === 'Active' ? 'success' : 'neutral'"
							:label="s.status"
							data-testid="sellos-shares-row-status"
						/>
					</div>
					<p class="mt-1 text-sm text-ink-muted">
						{{ s.all_units ? "All units" : `${s.units.length} chosen units` }};
						{{ s.share_price_list ? "price list" : "no price list" }};
						{{ s.brochures.length }} brochures.
						<span v-if="s.withdrawn_reason">Withdrawn: {{ s.withdrawn_reason }}</span>
					</p>
					<div
						v-if="s.status === 'Active'"
						class="mt-ui-sm flex flex-wrap items-end gap-ui-sm"
					>
						<FormField
							v-model="reasons[s.name]"
							label="Reason for a withdrawal (optional)"
							class="w-72"
							data-testid="sellos-shares-reason"
						/>
						<AppButton
							type="button"
							variant="danger"
							data-testid="sellos-shares-withdraw"
							@click="withdraw(s)"
						>
							Withdraw
						</AppButton>
					</div>
					<details class="mt-ui-sm">
						<summary class="cursor-pointer text-sm text-ink-muted">Log</summary>
						<ul class="mt-1 space-y-1 text-sm text-ink-muted">
							<li
								v-for="(l, i) in s.log"
								:key="i"
								data-testid="sellos-shares-log-row"
							>
								{{ l.changed_on }}: {{ l.changed_by_name }}, {{ l.action }}
								<span v-if="l.detail">({{ l.detail }})</span>
							</li>
						</ul>
					</details>
				</li>
			</ul>
		</ListCard>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import AppCheckbox from "../components/AppCheckbox.vue";
import EmptyState from "../components/EmptyState.vue";
import FormField from "../components/FormField.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { partnerSharesApi } from "../company/partnerSharesApi";
import { serverMessage } from "../crm/crmApi";

// The Company Admin's sharing of projects with channel partner firms (SOS-P7-03). Every change is made on the
// server and the list read back, so what is shown is what is saved.
const options = ref({ projects: [], firms: [], units: [], brochures: [], price_list: null });
const shares = ref([]);
const error = ref("");
const notice = ref("");
const loadError = ref("");
const loaded = ref(false);
const reasons = reactive({});
const form = reactive({
	project: "",
	every: false,
	firms: {},
	allUnits: true,
	units: {},
	priceList: false,
	brochures: {},
});

const projectOptions = computed(() =>
	options.value.projects.map((p) => ({ label: p.project_name, value: p.name }))
);
const unitLabel = (u) =>
	`${u.tower ? u.tower + " " : ""}${u.unit_number}, ${u.configuration || "unit"}`;
const ticked = (map) => Object.keys(map).filter((k) => map[k]);

async function load() {
	loadError.value = "";
	try {
		const data = await partnerSharesApi.options(form.project);
		options.value = data;
		shares.value = data.shares;
	} catch (e) {
		loadError.value = serverMessage(e, "The shares could not be loaded.");
	} finally {
		loaded.value = true;
	}
}

async function chooseProject() {
	Object.assign(form, {
		every: false,
		firms: {},
		allUnits: true,
		units: {},
		priceList: false,
		brochures: {},
	});
	await load();
}

async function share() {
	error.value = "";
	notice.value = "";
	const firms = form.every ? ["all"] : ticked(form.firms);
	try {
		await partnerSharesApi.share({
			project: form.project,
			firms,
			units: form.allUnits ? [] : ticked(form.units),
			sharePriceList: form.priceList,
			brochures: ticked(form.brochures),
		});
		notice.value = "The project was shared.";
		await chooseProject();
	} catch (e) {
		error.value = serverMessage(e, "The project could not be shared.");
	}
}

async function withdraw(s) {
	error.value = "";
	notice.value = "";
	try {
		await partnerSharesApi.withdraw(s.name, reasons[s.name] || "");
		delete reasons[s.name];
		notice.value = "The share was withdrawn.";
		await load();
	} catch (e) {
		error.value = serverMessage(e, "The share could not be withdrawn.");
	}
}

onMounted(load);
</script>
