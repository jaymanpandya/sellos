import { createRouter, createWebHistory } from "vue-router";

import { base, session } from "./session";
import { inAreas, personaFor, routeArea } from "./personas";

const HomePage = () => import("./pages/HomePage.vue");
const NoAccessPage = () => import("./pages/NoAccessPage.vue");

export function createAppRouter() {
	const router = createRouter({
		history: createWebHistory(base),
		routes: [
			{ path: "/", name: "home", component: HomePage, meta: { area: "home" } },
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
