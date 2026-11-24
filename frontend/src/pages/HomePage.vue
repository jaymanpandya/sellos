<template>
	<PageTemplate data-testid="sellos-home">
		<template #header>
			<PageHeader
				:title="`Welcome${session.fullName ? ', ' + session.fullName : ''}`"
				title-testid="sellos-home-welcome"
				text="Your day at a glance."
				icon="lucide-layout-dashboard"
			/>
		</template>

		<router-link
			v-if="showSetup"
			to="/company/setup"
			class="ui-card mb-ui-md block text-ink"
			data-testid="sellos-home-setup-banner"
		>
			Finish setting up your company. It takes a few minutes.
		</router-link>
		<!-- A Company Admin, Agent and Sales Manager: the dashboard reads what the role may already see. -->
		<CrmDashboard v-if="showDashboard" class="mb-ui-lg" />
		<!-- SOS-P1-26: an Agent and a Sales Manager also land on Today, the lists to work through. -->
		<template v-if="showToday">
			<h2 class="ui-card-heading mb-ui-md">Today's work</h2>
			<TodayPage />
		</template>
		<!-- Platform Admin, Client and Channel Partner: no CRM numbers, so the places they can go. -->
		<ListCard v-else-if="!showDashboard" title="Where to next" data-testid="sellos-home-links">
			<ul class="grid gap-ui-md sm:grid-cols-2 lg:grid-cols-3">
				<li v-for="item in quickLinks" :key="item.key">
					<router-link
						:to="item.to"
						class="flex min-h-touch items-center gap-ui-md rounded border border-line-soft bg-surface-faint p-ui-md text-ink no-underline transition hover:border-line hover:bg-brand-soft"
						:data-testid="`sellos-home-link-${item.key}`"
					>
						<span
							class="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded bg-brand-soft text-brand"
							aria-hidden="true"
						>
							<span
								:class="ICONS[item.key] || 'lucide-circle'"
								class="icon-inherit size-5"
							/>
						</span>
						<span class="font-medium">{{ item.label }}</span>
					</router-link>
				</li>
			</ul>
		</ListCard>

		<!-- The "Go to" rail, on the dashboard only: places the role may open (its own navigation). -->
		<template v-if="showDashboard" #rail>
			<ListCard title="Go to" data-testid="sellos-home-rail">
				<ul class="space-y-1">
					<li v-for="item in railLinks" :key="item.key">
						<router-link
							:to="item.to"
							class="flex min-h-touch items-center gap-ui-sm rounded px-ui-sm text-ink no-underline hover:bg-brand-soft"
							:data-testid="`sellos-home-rail-${item.key}`"
						>
							<span
								:class="ICONS[item.key] || 'lucide-circle'"
								class="icon-inherit size-4 text-ink-muted"
								aria-hidden="true"
							/>
							<span>{{ item.label }}</span>
						</router-link>
					</li>
				</ul>
			</ListCard>
		</template>
	</PageTemplate>
</template>

<script setup>
import { computed } from "vue";

import CrmDashboard from "../components/home/CrmDashboard.vue";
import ListCard from "../components/ListCard.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import { ICONS } from "../navIcons";
import { navFor, personaFor } from "../personas";
import { session } from "../session";
import TodayPage from "./TodayPage.vue";

const has = (role) => session.roles.includes(role);
const showSetup = computed(() => !session.setupComplete && has("SellOS Company Admin"));
const showToday = computed(() => has("SellOS Agent") || has("SellOS Sales Manager"));
// The three methods the dashboard calls (get_board, today_screen, caller_queue) allow exactly these roles.
const quickLinks = computed(() =>
	navFor(personaFor(session.roles)).filter((item) => item.key !== "home")
);
// The rail keeps to the everyday places, and only those this role's navigation already holds.
const RAIL_KEYS = ["leads", "queue", "whatsapp", "visits", "inventory", "reports"];
const railLinks = computed(() => quickLinks.value.filter((item) => RAIL_KEYS.includes(item.key)));
const showDashboard = computed(() => showToday.value || has("SellOS Company Admin"));
</script>
