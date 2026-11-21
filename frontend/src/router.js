import { createRouter, createWebHistory } from "vue-router";

import { base, session } from "./session";
import { inAreas, personaFor, routeArea } from "./personas";
import { loadPartnerState, partnerMayWork } from "./partnerState";
import { setPageTitle } from "./shell";

const HomePage = () => import("./pages/HomePage.vue");
const LeadsPage = () => import("./pages/LeadsPage.vue");
const LeadPage = () => import("./pages/LeadPage.vue");
const ImportLeadsPage = () => import("./pages/ImportLeadsPage.vue");
const CallQueuePage = () => import("./pages/CallQueuePage.vue");
const SiteVisitsPage = () => import("./pages/SiteVisitsPage.vue");
const SupportPage = () => import("./pages/SupportPage.vue");
const UsersPage = () => import("./pages/UsersPage.vue");
const TelephonyPage = () => import("./pages/TelephonyPage.vue");
const TeamsPage = () => import("./pages/TeamsPage.vue");
const AssignmentRulesPage = () => import("./pages/AssignmentRulesPage.vue");
const TeamReportPage = () => import("./pages/TeamReportPage.vue");
const CallReportsPage = () => import("./pages/CallReportsPage.vue");
const CallListsPage = () => import("./pages/CallListsPage.vue");
const PartnerFirmsPage = () => import("./pages/PartnerFirmsPage.vue");
const PartnerFirmPage = () => import("./pages/PartnerFirmPage.vue");
const TenantsPage = () => import("./pages/TenantsPage.vue");
const SetupWizardPage = () => import("./pages/SetupWizardPage.vue");
const NoAccessPage = () => import("./pages/NoAccessPage.vue");

export function createAppRouter() {
	const router = createRouter({
		history: createWebHistory(base),
		routes: [
			{
				path: "/",
				name: "home",
				component: HomePage,
				meta: { area: "home", title: "Home" },
			},
			// A lead replaces the list (SOS-UI-2B, it used to open under it). The list and the lead are sibling
			// routes, so the list is not on screen while a lead is; its filters ride along in the query and
			// "Back to leads" returns to them.
			{
				path: "/crm/leads",
				name: "leads",
				component: LeadsPage,
				meta: { area: "crm", title: "Leads" },
			},
			{
				path: "/crm/leads/:name",
				name: "lead",
				component: LeadPage,
				meta: { area: "crm", title: "Lead", crumb: "Leads" },
			},
			{
				path: "/crm/import",
				name: "import-leads",
				component: ImportLeadsPage,
				meta: { area: "crm", title: "Import leads" },
			},
			{
				path: "/crm/queue",
				name: "call-queue",
				component: CallQueuePage,
				meta: { area: "crm", title: "Call queue" },
			},
			{
				path: "/crm/visits",
				name: "site-visits",
				component: SiteVisitsPage,
				meta: { area: "crm", title: "Site visits" },
			},
			{
				path: "/partner/leads",
				name: "partner-leads",
				component: LeadsPage,
				meta: { area: "partner", title: "Leads" },
			},
			{
				path: "/partner/leads/:name",
				name: "partner-lead",
				component: LeadPage,
				meta: { area: "partner", title: "Lead", crumb: "Leads" },
			},
			{
				path: "/company/support",
				name: "support-access",
				component: SupportPage,
				meta: { area: "company", title: "Support access" },
			},
			{
				path: "/company/users",
				name: "users",
				component: UsersPage,
				meta: { area: "company", title: "Users" },
			},
			{
				path: "/company/telephony",
				name: "telephony",
				component: TelephonyPage,
				meta: { area: "company", title: "Telephony" },
			},
			{
				path: "/company/call-lists",
				name: "call-lists",
				component: CallListsPage,
				meta: { area: "company", title: "Call lists" },
			},
			{
				path: "/company/teams",
				name: "teams",
				component: TeamsPage,
				meta: { area: "company", title: "Teams" },
			},
			{
				path: "/company/partners",
				name: "partner-firms",
				component: PartnerFirmsPage,
				meta: { area: "company", title: "Channel partners" },
			},
			{
				path: "/partner/firm",
				name: "partner-firm",
				component: PartnerFirmPage,
				meta: { area: "partner", title: "Your firm" },
			},
			{
				path: "/company/assignment",
				name: "assignment-rules",
				component: AssignmentRulesPage,
				meta: { area: "company", title: "Assignment" },
			},
			{
				path: "/reports/team",
				name: "team-report",
				component: TeamReportPage,
				meta: { area: "reports", title: "Team report" },
			},
			{
				path: "/reports/calls",
				name: "call-reports",
				component: CallReportsPage,
				meta: { area: "reports", title: "Call reports" },
			},
			{
				path: "/company/setup",
				name: "setup-wizard",
				component: SetupWizardPage,
				meta: { area: "company", title: "Setup" },
			},
			{
				path: "/control/tenants",
				name: "tenants",
				component: TenantsPage,
				meta: { area: "platform", title: "Companies" },
			},
			{
				path: "/no-access",
				name: "no-access",
				component: NoAccessPage,
				meta: { area: "home", title: "No access" },
			},
		],
	});

	// Every route belongs to an area. A signed in user may only open the areas of their persona.
	router.beforeEach(async (to) => {
		if (to.name === "no-access") return true;
		const persona = personaFor(session.roles);
		if (!persona || !inAreas(persona, routeArea(to))) return { name: "no-access" };
		// SOS-P7-01: a partner whose firm is not Approved works nowhere but the page that says why.
		if (
			persona.key === "channel_partner" &&
			to.name !== "partner-firm" &&
			to.name !== "home"
		) {
			await loadPartnerState(true);
			if (!partnerMayWork()) return { name: "partner-firm" };
		}
		return true;
	});

	// The top bar's breadcrumb and the browser tab follow the route's title (a lead page sets its own).
	router.afterEach((to) => setPageTitle(to.meta.title || ""));

	return router;
}
