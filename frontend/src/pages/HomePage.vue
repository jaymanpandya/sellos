<template>
	<!-- A Company Admin, Agent and Sales Manager: the dashboard reads what the role may already see. -->
	<CrmDashboard v-if="showDashboard">
		<template #header>
			<PageHeader
				:title="welcome"
				title-testid="sellos-home-welcome"
				text="Your day at a glance."
				icon="lucide-layout-dashboard"
			/>
		</template>
		<template v-if="showSetup" #notice>
			<Notice
				tone="info"
				title="Finish setting up your company"
				testid="sellos-home-setup-banner"
			>
				It takes a few minutes.
				<router-link to="/company/setup" class="ui-link">Open the setup</router-link>
			</Notice>
		</template>
		<template #rail>
			<GoToCard
				:links="railLinks"
				test-prefix="sellos-home-rail"
				data-testid="sellos-home-rail"
			/>
		</template>
		<!-- SOS-P1-26: an Agent and a Sales Manager also land on Today, the lists to work through. -->
		<SectionCard v-if="showToday" title="Today's work">
			<TodayPage />
		</SectionCard>
	</CrmDashboard>

	<!-- Platform Admin, Client and Channel Partner: no CRM numbers, so the places they can go. -->
	<PageTemplate v-else shape="dashboard" data-testid="sellos-home">
		<template #header>
			<PageHeader
				:title="welcome"
				title-testid="sellos-home-welcome"
				text="Your day at a glance."
				icon="lucide-layout-dashboard"
			/>
		</template>
		<template #kpis>
			<KpiStrip :items="tiles" data-testid="sellos-home-kpis" />
		</template>
		<template #left>
			<SectionCard
				v-for="group in columns[0]"
				:key="group.key"
				:title="group.label"
				data-testid="sellos-home-links"
			>
				<ul class="ui-list">
					<HomeRow
						v-for="item in group.items"
						:key="item.key"
						:testid="`sellos-home-link-${item.key}`"
						:title="item.label"
						:line="`Go to ${item.label.toLowerCase()}`"
						:badge="group.label"
						:to="item.to"
					/>
				</ul>
			</SectionCard>
		</template>
		<template #right>
			<SectionCard v-for="group in columns[1]" :key="group.key" :title="group.label">
				<ul class="ui-list">
					<HomeRow
						v-for="item in group.items"
						:key="item.key"
						:testid="`sellos-home-link-${item.key}`"
						:title="item.label"
						:line="`Go to ${item.label.toLowerCase()}`"
						:badge="group.label"
						:to="item.to"
					/>
				</ul>
			</SectionCard>
		</template>
		<template #rail>
			<GoToCard
				:links="goLinks"
				test-prefix="sellos-home-rail"
				data-testid="sellos-home-rail"
			/>
		</template>
	</PageTemplate>
</template>

<script setup>
import { computed } from "vue";

import CrmDashboard from "../components/home/CrmDashboard.vue";
import GoToCard from "../components/home/GoToCard.vue";
import HomeRow from "../components/home/HomeRow.vue";
import KpiStrip from "../components/KpiStrip.vue";
import Notice from "../components/Notice.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import SectionCard from "../components/SectionCard.vue";
import { areaOfItem, areas } from "../areas";
import { ICONS } from "../navIcons";
import { navFor, personaFor } from "../personas";
import { session } from "../session";
import TodayPage from "./TodayPage.vue";

const has = (role) => session.roles.includes(role);
const welcome = computed(() => `Welcome${session.fullName ? ", " + session.fullName : ""}`);
const showSetup = computed(() => !session.setupComplete && has("SellOS Company Admin"));
const showToday = computed(() => has("SellOS Agent") || has("SellOS Sales Manager"));
const showDashboard = computed(() => showToday.value || has("SellOS Company Admin"));

// Only the places this role's own navigation already holds.
const quickLinks = computed(() =>
	navFor(personaFor(session.roles))
		.filter((item) => item.key !== "home")
		.map((item) => ({ ...item, icon: ICONS[item.key] || "lucide-circle" }))
);
// The Go to card keeps to the everyday places on the dashboard, and the first few elsewhere.
const RAIL_KEYS = ["leads", "queue", "whatsapp", "visits", "inventory", "reports"];
const railLinks = computed(() => quickLinks.value.filter((item) => RAIL_KEYS.includes(item.key)));
const goLinks = computed(() => quickLinks.value.slice(0, 6));

// The role's places grouped by area, spread over two columns of about the same length.
const groups = computed(() => {
	const byArea = new Map();
	for (const item of quickLinks.value) {
		const key = areaOfItem(item);
		if (!byArea.has(key)) byArea.set(key, { key, label: areas[key].label, items: [] });
		byArea.get(key).items.push(item);
	}
	return [...byArea.values()];
});
const columns = computed(() => {
	const cols = [[], []];
	const size = [0, 0];
	for (const group of groups.value) {
		const at = size[0] <= size[1] ? 0 : 1;
		cols[at].push(group);
		size[at] += group.items.length + 1;
	}
	return cols;
});
const tiles = computed(() =>
	groups.value.slice(0, 4).map((group) => ({
		label: group.label,
		value: group.items.length,
		caption: group.items
			.slice(0, 2)
			.map((item) => item.label)
			.join(", "),
		icon: areas[group.key].icon,
		to: group.items[0].to,
	}))
);
</script>
