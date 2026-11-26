import { createRouter, createWebHistory } from "vue-router";

import { base, session } from "./session";
import { inAreas, personaFor, routeArea } from "./personas";
import { loadPartnerState, partnerMayWork } from "./partnerState";
import { setPageTitle } from "./shell";

const HomePage = () => import("./pages/HomePage.vue");
const LeadsPage = () => import("./pages/LeadsPage.vue");
const SellersPage = () => import("./pages/SellersPage.vue");
const MandatesPage = () => import("./pages/MandatesPage.vue");
const DealsPage = () => import("./pages/DealsPage.vue");
const SellerPage = () => import("./pages/SellerPage.vue");
const MandatePage = () => import("./pages/MandatePage.vue");
const DealPage = () => import("./pages/DealPage.vue");
const LeadPage = () => import("./pages/LeadPage.vue");
const ImportLeadsPage = () => import("./pages/ImportLeadsPage.vue");
const CallQueuePage = () => import("./pages/CallQueuePage.vue");
const SiteVisitsPage = () => import("./pages/SiteVisitsPage.vue");
const SupportPage = () => import("./pages/SupportPage.vue");
const UsersPage = () => import("./pages/UsersPage.vue");
const CompanySettingsPage = () => import("./pages/CompanySettingsPage.vue");
const CompanyProfilePage = () => import("./pages/CompanyProfilePage.vue");
const TelephonyPage = () => import("./pages/TelephonyPage.vue");
const WhatsAppPage = () => import("./pages/WhatsAppPage.vue");
const WhatsAppSetupPage = () => import("./pages/WhatsAppSetupPage.vue");
const ResponseAlertsPage = () => import("./pages/ResponseAlertsPage.vue");
const TeamsPage = () => import("./pages/TeamsPage.vue");
const AssignmentRulesPage = () => import("./pages/AssignmentRulesPage.vue");
const TeamReportPage = () => import("./pages/TeamReportPage.vue");
const CallReportsPage = () => import("./pages/CallReportsPage.vue");
const BusinessReportsPage = () => import("./pages/BusinessReportsPage.vue");
const ReportsPage = () => import("./pages/ReportsPage.vue");
const CallListsPage = () => import("./pages/CallListsPage.vue");
const PartnerFirmsPage = () => import("./pages/PartnerFirmsPage.vue");
const PartnerRegistrationsPage = () => import("./pages/PartnerRegistrationsPage.vue");
const PartnerRegisterPage = () => import("./pages/PartnerRegisterPage.vue");
const PartnerFirmPage = () => import("./pages/PartnerFirmPage.vue");
const PartnerSharesPage = () => import("./pages/PartnerSharesPage.vue");
const PartnerSharedPage = () => import("./pages/PartnerSharedPage.vue");
const InventoryPage = () => import("./pages/InventoryPage.vue");
const ListingsPage = () => import("./pages/ListingsPage.vue");
const ImportInventoryPage = () => import("./pages/ImportInventoryPage.vue");
const ProjectPage = () => import("./pages/ProjectPage.vue");
const CostSheetPage = () => import("./pages/CostSheetPage.vue");
const TenantsPage = () => import("./pages/TenantsPage.vue");
const PartnerReportsPage = () => import("./pages/PartnerReportsPage.vue");
const CommissionPage = () => import("./pages/CommissionPage.vue");
const PartnerCommissionPage = () => import("./pages/PartnerCommissionPage.vue");
const PartnerEarningsPage = () => import("./pages/PartnerEarningsPage.vue");
const PlatformReportsPage = () => import("./pages/PlatformReportsPage.vue");
const SetupWizardPage = () => import("./pages/SetupWizardPage.vue");
const ClientOverviewPage = () => import("./pages/ClientOverviewPage.vue");
const ClientShortlistsPage = () => import("./pages/ClientShortlistsPage.vue");
const ClientShortlistPage = () => import("./pages/ClientShortlistPage.vue");
const NoAccessPage = () => import("./pages/NoAccessPage.vue");
const GalleryPage = () => import("./pages/GalleryPage.vue");

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
			// The design system gallery (docs/DESIGN_SYSTEM.md): every shared piece in every state. Not in the menu.
			{
				path: "/gallery",
				name: "gallery",
				component: GalleryPage,
				meta: { area: "profile", title: "Design system gallery" },
			},
			{
				path: "/crm/leads",
				name: "leads",
				component: LeadsPage,
				meta: { area: "crm", title: "Leads" },
			},
			{
				path: "/crm/sellers",
				name: "sellers",
				component: SellersPage,
				meta: { area: "crm", title: "Sellers" },
			},
			{
				path: "/crm/sellers/:name",
				name: "seller",
				component: SellerPage,
				meta: { area: "crm", title: "Seller", crumb: "Sellers" },
			},
			{
				path: "/crm/mandates",
				name: "mandates",
				component: MandatesPage,
				meta: { area: "crm", title: "Mandates" },
			},
			{
				path: "/crm/mandates/:name",
				name: "mandate",
				component: MandatePage,
				meta: { area: "crm", title: "Mandate", crumb: "Mandates" },
			},
			{
				path: "/crm/deals",
				name: "deals",
				component: DealsPage,
				meta: { area: "crm", title: "Deals" },
			},
			{
				path: "/crm/deals/:name",
				name: "deal",
				component: DealPage,
				meta: { area: "crm", title: "Deal", crumb: "Deals" },
			},
			{
				// SOS-P7-04: commission rates and payouts.
				path: "/crm/commission",
				name: "commission",
				component: CommissionPage,
				meta: { area: "crm", title: "Commission" },
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
				path: "/company/settings",
				name: "company-settings",
				component: CompanySettingsPage,
				meta: { area: "company", title: "Company settings" },
			},
			{
				path: "/company/profile",
				name: "company-profile",
				component: CompanyProfilePage,
				meta: { area: "company", title: "Company profile" },
			},
			{
				path: "/company/telephony",
				name: "telephony",
				component: TelephonyPage,
				meta: { area: "company", title: "Telephony" },
			},
			{
				path: "/company/whatsapp",
				name: "whatsapp-setup",
				component: WhatsAppSetupPage,
				meta: { area: "company", title: "WhatsApp setup" },
			},
			{
				path: "/crm/whatsapp",
				name: "whatsapp",
				component: WhatsAppPage,
				meta: { area: "crm", title: "WhatsApp" },
			},
			{
				path: "/company/response-alerts",
				name: "response-alerts",
				component: ResponseAlertsPage,
				meta: { area: "company", title: "Response time alerts" },
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
				path: "/inventory",
				name: "inventory",
				component: InventoryPage,
				meta: { area: "inventory", title: "Inventory" },
			},
			{
				path: "/inventory/import",
				name: "import-inventory",
				component: ImportInventoryPage,
				meta: { area: "inventory", title: "Import inventory", crumb: "Inventory" },
			},
			{
				path: "/inventory/listings",
				name: "listings",
				component: ListingsPage,
				meta: { area: "inventory", title: "Listings", crumb: "Inventory" },
			},
			{
				path: "/inventory/projects/:name",
				name: "project",
				component: ProjectPage,
				meta: { area: "inventory", title: "Project", crumb: "Inventory" },
			},
			{
				path: "/inventory/units/:unit/cost-sheet",
				name: "cost-sheet",
				component: CostSheetPage,
				meta: { area: "inventory", title: "Cost sheet", crumb: "Inventory" },
			},
			{
				path: "/company/partners",
				name: "partner-firms",
				component: PartnerFirmsPage,
				meta: { area: "company", title: "Channel partners" },
			},
			{
				path: "/company/registrations",
				name: "partner-registrations",
				component: PartnerRegistrationsPage,
				meta: { area: "company", title: "Partner registrations" },
			},
			{
				path: "/company/shares",
				name: "partner-shares",
				component: PartnerSharesPage,
				meta: { area: "company", title: "Share with partners" },
			},
			{
				path: "/partner/shared",
				name: "partner-shared",
				component: PartnerSharedPage,
				meta: { area: "partner", title: "Shared projects" },
			},
			{
				path: "/partner/register",
				name: "partner-register",
				component: PartnerRegisterPage,
				meta: { area: "partner", title: "Register a buyer" },
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
				// SOS-P5-01: the report engine. Its own area, so the Agent reads it and not the call reports.
				path: "/reports",
				name: "reports",
				component: ReportsPage,
				meta: { area: "insights", title: "Reports" },
			},
			{
				// SOS-P5-02: the Company Admin's funnel, source, productivity and ageing reports.
				path: "/reports/business",
				name: "business-reports",
				component: BusinessReportsPage,
				meta: { area: "reports", title: "Business reports" },
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
				// SOS-P5-03: the Platform Admin's totals per company, on the control site.
				path: "/control/reports",
				name: "platform-reports",
				component: PlatformReportsPage,
				meta: { area: "platform", title: "Platform reports" },
			},
			{
				// SOS-P5-03: a partner's own leads, deals and commission statements.
				path: "/partner/reports",
				name: "partner-reports",
				component: PartnerReportsPage,
				meta: { area: "partner", title: "Your results" },
			},
			{
				// SOS-P5-06: a partner's own deals, earnings and QR code.
				path: "/partner/earnings",
				name: "partner-earnings",
				component: PartnerEarningsPage,
				meta: { area: "partner", title: "Your deals and earnings" },
			},
			{
				// SOS-P7-04: a partner's own commission statement.
				path: "/partner/commission",
				name: "partner-commission",
				component: PartnerCommissionPage,
				meta: { area: "partner", title: "Your commission" },
			},
			{
				// SOS-P5-05: a client's own shortlists, visits, deal status, mandate and enquiries.
				path: "/client/overview",
				name: "client-overview",
				component: ClientOverviewPage,
				meta: { area: "client", title: "Your dealings" },
			},
			{
				path: "/client/shortlists",
				name: "client-shortlists",
				component: ClientShortlistsPage,
				meta: { area: "client", title: "Your shortlists" },
			},
			{
				path: "/client/shortlists/:name",
				name: "client-shortlist",
				component: ClientShortlistPage,
				meta: { area: "client", title: "Shortlist", crumb: "Your shortlists" },
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
