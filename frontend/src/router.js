import { createRouter, createWebHistory } from "vue-router";

import { base, session } from "./session";
import { inAreas, personaFor, routeArea } from "./personas";

const HomePage = () => import("./pages/HomePage.vue");
const LeadsPage = () => import("./pages/LeadsPage.vue");
const LeadPage = () => import("./pages/LeadPage.vue");
const SupportPage = () => import("./pages/SupportPage.vue");
const NoAccessPage = () => import("./pages/NoAccessPage.vue");

export function createAppRouter() {
	const router = createRouter({
		history: createWebHistory(base),
		routes: [
			{ path: "/", name: "home", component: HomePage, meta: { area: "home" } },
			// A lead opens beside the list, so the list stays on screen (SOS-P1-06A).
			{
				path: "/crm/leads",
				name: "leads",
				component: LeadsPage,
				meta: { area: "crm" },
				children: [{ path: ":name", name: "lead", component: LeadPage }],
			},
			{
				path: "/partner/leads",
				name: "partner-leads",
				component: LeadsPage,
				meta: { area: "partner" },
				children: [{ path: ":name", name: "partner-lead", component: LeadPage }],
			},
			{
				path: "/company/support",
				name: "support-access",
				component: SupportPage,
				meta: { area: "company" },
			},
			{
				path: "/no-access",
				name: "no-access",
				component: NoAccessPage,
				meta: { area: "home" },
			},
		],
	});

	// Every route belongs to an area. A signed in user may only open the areas of their persona.
	router.beforeEach((to) => {
		if (to.name === "no-access") return true;
		const persona = personaFor(session.roles);
		if (!persona || !inAreas(persona, routeArea(to))) return { name: "no-access" };
		return true;
	});

	return router;
}
