<template>
	<PageTemplate shape="dashboard" data-testid="sellos-home">
		<template #header><slot name="header" /></template>
		<template v-if="$slots.notice" #notice><slot name="notice" /></template>

		<template #kpis>
			<KpiStrip v-if="loaded" :items="kpis" data-testid="sellos-dash-kpis" />
			<!-- The first load: tiles in the shape of the numbers, at every width including 390 (SOS-LOOP). -->
			<LoadingSkeleton
				v-else-if="!error"
				variant="cards"
				:rows="4"
				label="Getting your numbers"
				data-testid="sellos-dash-loading"
			/>
		</template>

		<template #left>
			<div data-testid="sellos-dash">
				<LoadError
					v-if="error"
					data-testid="sellos-dash-error"
					:message="error"
					@retry="load"
				/>
				<LoadingSkeleton v-else-if="!loaded" :rows="4" />
			</div>
			<template v-if="loaded">
				<SectionCard title="Leads by stage" data-testid="sellos-dash-stages">
					<EmptyState
						v-if="!board.total"
						title="No leads in the pipeline yet."
						text="New leads appear here by stage as soon as they are added."
						icon="lucide-users"
					/>
					<StageBars v-else :columns="board.columns" />
					<template #footer>
						<router-link to="/crm/leads" class="ui-link">Open leads</router-link>
					</template>
				</SectionCard>

				<SectionCard
					title="Consent warnings, buyer leads"
					data-testid="sellos-dash-consent"
				>
					<EmptyState
						v-if="!warned.length"
						title="No consent warnings."
						text="Every buyer lead you can see has a live consent record."
						icon="lucide-shield-check"
					/>
					<template v-else>
						<p class="mb-ui-sm ui-text-muted">
							<b class="ui-text-strong" data-testid="sellos-dash-consent-count">{{
								warned.length
							}}</b>
							of {{ buyers.length }} buyer leads carry a warning. Calls and SMS still
							go ahead. After a WhatsApp STOP nothing is sent on WhatsApp unprompted.
						</p>
						<ul class="ui-list">
							<HomeRow
								v-for="row in warned.slice(0, 5)"
								:key="row.lead"
								testid="sellos-dash-consent-row"
								:title="row.lead_name || row.lead_title"
								:source="row.lead_source"
								:line="row.consent_message || 'Consent status'"
								:badge="row.consent_status"
								:badge-tone="row.consent_warning === 'red' ? 'danger' : 'warning'"
								:badge-title="row.consent_message"
								:to="`/crm/leads/${row.lead}`"
							/>
						</ul>
					</template>
				</SectionCard>
			</template>
		</template>

		<template #right>
			<!-- With the Today worklist below (Agent, Sales Manager) these two cards would repeat it. -->
			<template v-if="loaded && !worklist">
				<SectionCard title="Follow ups overdue" data-testid="sellos-dash-overdue">
					<EmptyState
						v-if="!overdue.length"
						title="Nothing overdue."
						text="Every follow up due so far has been done."
						icon="lucide-clock-alert"
					/>
					<ul v-else class="ui-list">
						<HomeRow
							v-for="row in overdue.slice(0, 5)"
							:key="row.name || row.lead"
							testid="sellos-dash-overdue-row"
							:title="row.lead_name || row.lead_title"
							:source="row.lead_source"
							:line="`Due ${formatWhen(row.due_at || row.due_date)}`"
							badge="Overdue"
							badge-tone="danger"
							:to="`/crm/leads/${row.lead}`"
						/>
					</ul>
				</SectionCard>

				<SectionCard title="Today's site visits" data-testid="sellos-dash-visits">
					<EmptyState
						v-if="!today.visits_today.length"
						title="No site visits today."
						text="Book one from a lead and it shows here on the day."
						icon="lucide-calendar-check"
					/>
					<ul v-else class="ui-list">
						<HomeRow
							v-for="row in today.visits_today.slice(0, 5)"
							:key="row.name"
							testid="sellos-dash-visit-row"
							:title="row.lead_name || row.lead_title"
							:source="row.lead_source"
							:line="formatDateTime(row.visit_datetime)"
							badge="Today"
							badge-tone="info"
							:to="`/crm/leads/${row.lead}`"
						/>
					</ul>
				</SectionCard>
			</template>
		</template>

		<template #rail><slot name="rail" /></template>

		<!-- SOS-P1-26: an Agent and a Sales Manager also land on Today, the lists to work through. -->
		<slot />
	</PageTemplate>
</template>

<script setup>
// The Home dashboard of a Company Admin, Agent and Sales Manager. It reads three existing methods, as
// the Leads board, the Today screen and the caller queue do, and changes nothing. Each role sees what it
// may already see there: its own, its team's, or the whole company's.
import { computed, onMounted, ref } from "vue";

import EmptyState from "../EmptyState.vue";
import KpiStrip from "../KpiStrip.vue";
import LoadError from "../LoadError.vue";
import LoadingSkeleton from "../LoadingSkeleton.vue";
import PageTemplate from "../PageTemplate.vue";
import SectionCard from "../SectionCard.vue";
import HomeRow from "./HomeRow.vue";
import StageBars from "./StageBars.vue";
import { crmApi, serverMessage } from "../../crm/crmApi";
import { formatDateTime, formatWhen } from "../../format";

defineProps({
	// True when the page shows the Today worklist below, which already holds follow ups and visits.
	worklist: { type: Boolean, default: false },
});
const loaded = ref(false);
const error = ref("");
const board = ref({ columns: [], total: 0 });
const today = ref({ counts: {}, follow_ups: [], visits_today: [] });
const queue = ref({ total: 0, leads: [] });

const overdue = computed(() => today.value.follow_ups.filter((row) => row.state === "overdue"));
// One population for the Leads tile and the consent card: the buyer leads (the Buyer pipeline).
const buyers = computed(() => queue.value.leads.filter((row) => row.pipeline !== "Seller"));
const warned = computed(() => buyers.value.filter((row) => row.consent_warning));
const kpis = computed(() => [
	{
		key: "leads",
		testid: "sellos-dash-kpi-leads",
		valueTestid: "sellos-dash-kpi-leads",
		label: "Buyer leads",
		value: board.value.total,
		caption: "In the buyer pipeline",
		icon: "lucide-users",
		tone: "",
		to: "/crm/leads",
	},
	{
		key: "new",
		testid: "sellos-dash-kpi-new",
		valueTestid: "sellos-dash-kpi-new",
		label: "New leads",
		value: today.value.counts.new_leads || 0,
		caption: "Waiting for a first call",
		icon: "lucide-user-plus",
		tone: "success",
		to: "/crm/queue",
	},
	{
		key: "overdue",
		testid: "sellos-dash-kpi-overdue",
		valueTestid: "sellos-dash-kpi-overdue",
		label: "Follow ups overdue",
		value: overdue.value.length,
		caption: `${today.value.counts.follow_ups || 0} due today or earlier`,
		icon: "lucide-clock-alert",
		tone: "danger",
		to: "/crm/queue",
	},
	{
		key: "visits",
		testid: "sellos-dash-kpi-visits",
		valueTestid: "sellos-dash-kpi-visits",
		label: "Site visits today",
		value: today.value.counts.visits_today || 0,
		caption: `${today.value.counts.visits_tomorrow || 0} tomorrow`,
		icon: "lucide-calendar-check",
		tone: "info",
		to: "/crm/visits",
	},
]);

async function load() {
	error.value = "";
	loaded.value = false;
	try {
		const [b, t, q] = await Promise.all([
			crmApi.getBoard(),
			crmApi.todayScreen(),
			crmApi.callerQueue(),
		]);
		board.value = b;
		today.value = t;
		queue.value = q;
		loaded.value = true;
	} catch (e) {
		error.value = serverMessage(e, "The dashboard could not be loaded.");
	}
}

onMounted(load);
</script>
