// The six roles. Each role is a persona with its own areas of the app and navigation. Roles are
// listed in priority order: a user with several roles gets the first one that matches.
export const PERSONAS = [
	{
		key: "platform_admin",
		role: "SellOS Platform Admin",
		areas: ["platform", "home", "profile"],
		nav: [
			{ key: "home", label: "Home", to: "/", area: "home" },
			{ key: "tenants", label: "Companies", to: "/control/tenants", area: "platform" },
			// SOS-P5-03: companies, usage and calling spend as totals per company.
			{
				key: "platform-reports",
				label: "Reports",
				to: "/control/reports",
				area: "platform",
			},
		],
	},
	{
		key: "company_admin",
		role: "SellOS Company Admin",
		areas: ["company", "crm", "inventory", "reports", "insights", "home", "profile"],
		nav: [
			{ key: "home", label: "Home", to: "/", area: "home" },
			{ key: "leads", label: "Leads", to: "/crm/leads", area: "crm" },
			{ key: "sellers", label: "Sellers", to: "/crm/sellers", area: "crm" },
			{ key: "mandates", label: "Mandates", to: "/crm/mandates", area: "crm" },
			{ key: "queue", label: "Call queue", to: "/crm/queue", area: "crm" },
			{ key: "whatsapp", label: "WhatsApp", to: "/crm/whatsapp", area: "crm" },
			{ key: "visits", label: "Site visits", to: "/crm/visits", area: "crm" },
			{ key: "import", label: "Import leads", to: "/crm/import", area: "crm" },
			{ key: "inventory", label: "Inventory", to: "/inventory", area: "inventory" },
			{ key: "users", label: "Users", to: "/company/users", area: "company" },
			{ key: "support", label: "Support access", to: "/company/support", area: "company" },
			{ key: "telephony", label: "Telephony", to: "/company/telephony", area: "company" },
			{
				key: "whatsapp-setup",
				label: "WhatsApp setup",
				to: "/company/whatsapp",
				area: "company",
			},
			{
				key: "response-alerts",
				label: "Response alerts",
				to: "/company/response-alerts",
				area: "company",
			},
			{ key: "call-lists", label: "Call lists", to: "/company/call-lists", area: "company" },
			{ key: "teams", label: "Teams", to: "/company/teams", area: "company" },
			{
				key: "partners",
				label: "Channel partners",
				to: "/company/partners",
				area: "company",
			},
			{
				key: "shares",
				label: "Share with partners",
				to: "/company/shares",
				area: "company",
			},
			{
				key: "registrations",
				label: "Partner registrations",
				to: "/company/registrations",
				area: "company",
			},
			{ key: "assignment", label: "Assignment", to: "/company/assignment", area: "company" },
			{ key: "call-reports", label: "Call reports", to: "/reports/calls", area: "reports" },
			// SOS-P5-01: the report engine, for every role that works leads.
			{ key: "reports", label: "Reports", to: "/reports", area: "insights" },
		],
	},
	{
		// SOS-P1-18: a manager works on the leads of its own team and reads the team's report.
		key: "sales_manager",
		role: "SellOS Sales Manager",
		areas: ["crm", "inventory", "reports", "insights", "home", "profile"],
		nav: [
			{ key: "home", label: "Home", to: "/", area: "home" },
			{ key: "leads", label: "Leads", to: "/crm/leads", area: "crm" },
			{ key: "sellers", label: "Sellers", to: "/crm/sellers", area: "crm" },
			{ key: "queue", label: "Call queue", to: "/crm/queue", area: "crm" },
			{ key: "whatsapp", label: "WhatsApp", to: "/crm/whatsapp", area: "crm" },
			{ key: "visits", label: "Site visits", to: "/crm/visits", area: "crm" },
			{ key: "inventory", label: "Inventory", to: "/inventory", area: "inventory" },
			{ key: "team-report", label: "Team report", to: "/reports/team", area: "reports" },
			{ key: "reports", label: "Reports", to: "/reports", area: "insights" },
		],
	},
	{
		key: "agent",
		role: "SellOS Agent",
		areas: ["crm", "inventory", "insights", "home", "profile"],
		nav: [
			{ key: "home", label: "Home", to: "/", area: "home" },
			{ key: "leads", label: "Leads", to: "/crm/leads", area: "crm" },
			{ key: "sellers", label: "Sellers", to: "/crm/sellers", area: "crm" },
			{ key: "mandates", label: "Mandates", to: "/crm/mandates", area: "crm" },
			{ key: "queue", label: "Call queue", to: "/crm/queue", area: "crm" },
			{ key: "whatsapp", label: "WhatsApp", to: "/crm/whatsapp", area: "crm" },
			{ key: "visits", label: "Site visits", to: "/crm/visits", area: "crm" },
			{ key: "inventory", label: "Inventory", to: "/inventory", area: "inventory" },
			{ key: "reports", label: "Reports", to: "/reports", area: "insights" },
		],
	},
	{
		key: "channel_partner",
		role: "SellOS Channel Partner",
		areas: ["partner", "home", "profile"],
		nav: [
			{ key: "home", label: "Home", to: "/", area: "home" },
			{ key: "firm", label: "Your firm", to: "/partner/firm", area: "partner" },
			{
				key: "register",
				label: "Register a buyer",
				to: "/partner/register",
				area: "partner",
			},
			{ key: "shared", label: "Shared projects", to: "/partner/shared", area: "partner" },
			{ key: "leads", label: "Leads", to: "/partner/leads", area: "partner" },
			// SOS-P5-03: the partner's own leads, deals and commission statements.
			{ key: "results", label: "Your results", to: "/partner/reports", area: "partner" },
		],
	},
	{
		key: "client",
		role: "SellOS Client",
		areas: ["client", "home", "profile"],
		nav: [
			{ key: "home", label: "Home", to: "/", area: "home" },
			{ key: "shortlists", label: "Shortlists", to: "/client/shortlists", area: "client" },
		],
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
