// The five roles. Each role is a persona with its own areas of the app and navigation. Roles are
// listed in priority order: a user with several roles gets the first one that matches.
export const PERSONAS = [
	{
		key: "platform_admin",
		role: "SellOS Platform Admin",
		areas: ["platform", "home", "profile"],
		nav: [{ key: "home", label: "Home", to: "/", area: "home" }],
	},
	{
		key: "company_admin",
		role: "SellOS Company Admin",
		areas: ["company", "crm", "reports", "home", "profile"],
		nav: [
			{ key: "home", label: "Home", to: "/", area: "home" },
			{ key: "leads", label: "Leads", to: "/crm/leads", area: "crm" },
			{ key: "support", label: "Support access", to: "/company/support", area: "company" },
		],
	},
	{
		key: "agent",
		role: "SellOS Agent",
		areas: ["crm", "home", "profile"],
		nav: [
			{ key: "home", label: "Home", to: "/", area: "home" },
			{ key: "leads", label: "Leads", to: "/crm/leads", area: "crm" },
		],
	},
	{
		key: "channel_partner",
		role: "SellOS Channel Partner",
		areas: ["partner", "home", "profile"],
		nav: [
			{ key: "home", label: "Home", to: "/", area: "home" },
			{ key: "leads", label: "Leads", to: "/partner/leads", area: "partner" },
		],
	},
	{
		key: "client",
		role: "SellOS Client",
		areas: ["client", "home", "profile"],
		nav: [{ key: "home", label: "Home", to: "/", area: "home" }],
	},
];

export function personaFor(roles = []) {
	return PERSONAS.find((p) => roles.includes(p.role)) || null;
}

export function routeArea(route) {
	return route?.meta?.area || "home";
}

export function inAreas(persona, area) {
	return Boolean(persona && persona.areas.includes(area));
}

export function navLabel(persona, key) {
	return persona?.nav.find((item) => item.key === key)?.label || key;
}

// The navigation a persona may use. An item shows only when its area is one of the persona's areas.
export function navFor(persona) {
	return (persona?.nav || []).filter((item) => inAreas(persona, item.area));
}
