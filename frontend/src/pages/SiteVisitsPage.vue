<template>
	<div class="max-w-4xl" data-testid="sellos-visits-page">
		<h1 class="ui-page-title">Site visits</h1>
		<p class="mt-2 text-ink-muted">{{ scopeNote }}</p>
		<p v-if="error" role="alert" data-testid="sellos-visits-error" class="mt-3 text-accent">
			{{ error }}
		</p>

		<section class="mt-4 rounded-input border border-line bg-surface p-4">
			<h2 class="font-medium text-ink">Tomorrow's visits to confirm</h2>
			<p class="text-sm text-ink-muted" data-testid="sellos-visits-tomorrow-date">
				{{ tomorrow ? dayLabel(tomorrow.date) : "" }}
			</p>
			<p
				v-if="tomorrow && !tomorrow.visits.length"
				data-testid="sellos-visits-tomorrow-empty"
				class="mt-2 text-ink-muted"
			>
				No visits tomorrow.
			</p>
			<ul class="mt-2 space-y-2" data-testid="sellos-visits-tomorrow">
				<li
					v-for="v in tomorrow?.visits || []"
					:key="v.name"
					data-testid="sellos-visits-tomorrow-item"
					class="rounded-input border border-line p-3"
				>
					<div class="flex flex-wrap items-center justify-between gap-2">
						<span class="text-ink">
							<router-link :to="`/crm/leads/${v.lead}`" class="underline">{{
								v.lead_title
							}}</router-link>
							, {{ v.project_name }} at {{ timeOf(v.visit_datetime) }}
							<span class="text-sm text-ink-muted">, {{ v.agent_name }}</span>
						</span>
						<span
							data-testid="sellos-visits-tomorrow-status"
							class="rounded-input border border-line px-2 py-1 text-xs text-ink"
							>{{ v.confirmation_status }}</span
						>
					</div>
					<VisitConfirm
						class="mt-2"
						:visit="v"
						:confirmations="options.confirmations"
						@changed="loadAll"
					/>
				</li>
			</ul>
		</section>

		<section class="mt-6 rounded-input border border-line bg-surface p-4">
			<div class="flex flex-wrap items-center justify-between gap-2">
				<h2 class="font-medium text-ink">Calendar</h2>
				<div class="flex flex-wrap gap-2">
					<button
						v-for="v in ['day', 'week']"
						:key="v"
						type="button"
						class="btn"
						:aria-pressed="view === v"
						:data-testid="`sellos-visits-view-${v}`"
						@click="setView(v)"
					>
						{{ v === "day" ? "Day" : "Week" }}
					</button>
					<button
						type="button"
						class="btn"
						data-testid="sellos-visits-prev"
						@click="step(-1)"
					>
						Previous
					</button>
					<button
						type="button"
						class="btn"
						data-testid="sellos-visits-today"
						@click="goToday"
					>
						Today
					</button>
					<button
						type="button"
						class="btn"
						data-testid="sellos-visits-next"
						@click="step(1)"
					>
						Next
					</button>
				</div>
			</div>
			<p class="mt-1 text-sm text-ink-muted" data-testid="sellos-visits-range">
				{{ calendar ? rangeLabel : "" }}
			</p>
			<ul class="mt-2 space-y-2" data-testid="sellos-visits-calendar">
				<li
					v-for="d in calendar?.days || []"
					:key="d.date"
					data-testid="sellos-visits-day"
					:data-date="d.date"
					class="rounded-input border border-line p-3"
				>
					<p class="text-sm font-medium text-ink">{{ dayLabel(d.date) }}</p>
					<p v-if="!d.visits.length" class="text-sm text-ink-muted">No visits.</p>
					<ul class="space-y-1">
						<li
							v-for="v in d.visits"
							:key="v.name"
							data-testid="sellos-visits-item"
							class="text-sm text-ink"
						>
							{{ timeOf(v.visit_datetime) }}
							<router-link :to="`/crm/leads/${v.lead}`" class="underline">{{
								v.lead_title
							}}</router-link>
							, {{ v.project_name }}, {{ v.agent_name }}
							<span class="text-ink-muted"
								>({{
									v.status === "Scheduled" ? v.confirmation_status : v.status
								}})</span
							>
						</li>
					</ul>
				</li>
			</ul>
		</section>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import VisitConfirm from "../components/VisitConfirm.vue";
import { crmApi, serverMessage } from "../crm/crmApi";
import { session } from "../session";

// SOS-P1-25: the calendar of visits by day and week, and tomorrow's visits to confirm. The server
// decides whose visits are listed: an Agent's own, a Sales Manager's team's, a Company Admin's everyone's.
const view = ref("week");
const date = ref(null); // a day of the window shown. null is today.
const calendar = ref(null);
const tomorrow = ref(null);
const options = ref({ confirmations: [] });
const error = ref("");

const scopeNote = computed(() => {
	if (session.roles.includes("SellOS Company Admin")) return "Everyone's site visits.";
	if (session.roles.includes("SellOS Sales Manager")) return "Your team's site visits.";
	return "Your site visits.";
});
const rangeLabel = computed(() =>
	calendar.value.start === calendar.value.end
		? dayLabel(calendar.value.start)
		: `${dayLabel(calendar.value.start)} to ${dayLabel(calendar.value.end)}`
);

function dayLabel(value) {
	const day = new Date(`${String(value).slice(0, 10)}T00:00:00`);
	return day.toLocaleDateString("en-IN", {
		weekday: "short",
		day: "numeric",
		month: "short",
		year: "numeric",
	});
}

function timeOf(value) {
	return String(value).slice(11, 16);
}

function shift(day, days) {
	const next = new Date(`${day}T00:00:00`);
	next.setDate(next.getDate() + days);
	const pad = (n) => String(n).padStart(2, "0");
	return `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}`;
}

// Only the newest request may fill the screen: a slower, older answer (the week the page opened
// with) must not overwrite the day the user has since chosen.
let latestLoad = 0;

async function loadAll() {
	const mine = ++latestLoad;
	error.value = "";
	try {
		const [cal, tom] = await Promise.all([
			crmApi.siteVisitCalendar(view.value, date.value),
			crmApi.tomorrowsSiteVisits(),
		]);
		if (mine !== latestLoad) return;
		calendar.value = cal;
		tomorrow.value = tom;
	} catch (e) {
		if (mine !== latestLoad) return;
		error.value = serverMessage(e, "The site visits could not be loaded.");
	}
}

function setView(next) {
	view.value = next;
	loadAll();
}

function step(direction) {
	const first = calendar.value.start;
	date.value = shift(first, direction * (view.value === "week" ? 7 : 1));
	loadAll();
}

function goToday() {
	date.value = null;
	loadAll();
}

onMounted(async () => {
	try {
		options.value = await crmApi.siteVisitOptions();
	} catch (e) {
		error.value = serverMessage(e, "The site visit lists could not be loaded.");
	}
	await loadAll();
});
</script>
