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
			{ key: "deals", label: "Deals", to: "/crm/deals", area: "crm" },
			// SOS-P7-04: commission rates and payouts.
			{ key: "commission", label: "Commission", to: "/crm/commission", area: "crm" },
			{ key: "queue", label: "Call queue", to: "/crm/queue", area: "crm" },
			{ key: "whatsapp", label: "WhatsApp", to: "/crm/whatsapp", area: "crm" },
			{ key: "visits", label: "Site visits", to: "/crm/visits", area: "crm" },
			{ key: "import", label: "Import leads", to: "/crm/import", area: "crm" },
			{
				key: "inventory",
				label: "Projects and listings",
				to: "/inventory",
				area: "inventory",
			},
			{
				key: "inventory-import",
				label: "Import inventory",
				to: "/inventory/import",
				area: "inventory",
			},
			{ key: "users", label: "Users", to: "/company/users", area: "company" },
			{
				key: "company-profile",
				label: "Company profile",
				to: "/company/profile",
				area: "company",
			},
			{
				key: "settings",
				label: "Company settings",
				to: "/company/settings",
				area: "company",
			},
			{
				key: "integrations",
				label: "Integrations",
				to: "/company/integrations",
				area: "company",
			},
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
			// SOS-P5-02: funnel, source performance, agent productivity and ageing.
			{
				key: "business-reports",
				label: "Business reports",
				to: "/reports/business",
				area: "reports",
			},
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
			{
				key: "inventory",
				label: "Projects and listings",
				to: "/inventory",
				area: "inventory",
			},
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
			{
				key: "inventory",
				label: "Projects and listings",
				to: "/inventory",
				area: "inventory",
			},
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
			// SOS-P5-06: the partner's own deals, earnings so far, potential earnings and QR code.
			{
				key: "earnings",
				label: "Deals and earnings",
				to: "/partner/earnings",
				area: "partner",
			},
			// SOS-P7-04: the partner's own payouts and statement.
			{
				key: "commission",
				label: "Your commission",
				to: "/partner/commission",
				area: "partner",
			},
		],
	},
	{
		key: "client",
		role: "SellOS Client",
		areas: ["client", "home", "profile"],
		nav: [
			{ key: "home", label: "Home", to: "/", area: "home" },
			// SOS-P5-05: shortlists, visits, deal and mandate status, and enquiries on the client's property.
			{ key: "overview", label: "Your dealings", to: "/client/overview", area: "client" },
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

// What a menu group is called for a persona. The shared area names ("Leads and Sales") describe a company's
// work; a Client and a Channel Partner see names for what the group is to them (SOS-LOOP).
const GROUP_LABELS = {
	client: { sales: "Your dealings" },
	channel_partner: { sales: "Your firm", money: "Your earnings" },
};
export const groupLabel = (persona, areaKey, fallback) =>
	GROUP_LABELS[persona?.key]?.[areaKey] || fallback;
