// SOS-P0-10: the layout works at phone width (390 px wide). The side navigation gives way to a top bar
// and a bottom navigation, and nothing scrolls sideways.
const BELL_ROLES = ["company_admin", "sales_manager", "agent", "channel_partner"];
const ROLES = [
	"platform_admin",
	"company_admin",
	"sales_manager",
	"agent",
	"channel_partner",
	"client",
];

const stubBell = () =>
	cy
		.intercept("**/api/method/sellos.crm.api.list_notifications*", {
			body: { message: { unread: 0, items: [] } },
		})
		.as("notifications");

// SOS-P1-26: an agent and a sales manager land on Today, which asks for three lists. Stub them all and
// wait for them, so no real request is still running when the test ends (a slow CI run cut it off).
const stubToday = () => {
	cy.intercept("**/api/method/sellos.crm.api.list_call_outcomes*", {
		body: { message: { outcomes: [] } },
	}).as("outcomes");
	cy.intercept("**/api/method/sellos.crm.api.site_visit_options*", {
		body: { message: { confirmations: [] } },
	}).as("visitOptions");
	cy.intercept("**/api/method/sellos.crm.api.today_screen*", {
		body: {
			message: {
				scope: "own",
				counts: { follow_ups: 0, new_leads: 0, visits_today: 0, visits_tomorrow: 0 },
				follow_ups: [],
				new_leads: [],
				visits_today: [],
				visits_tomorrow: [],
			},
		},
	}).as("today");
};
const todayLoaded = () => {
	cy.wait("@outcomes");
	cy.wait("@visitOptions");
	cy.wait("@today");
};

context("SOS-P0-10: phone layout", () => {
	beforeEach(() => {
		cy.viewport(390, 844);
	});

	ROLES.forEach((role) => {
		it(`${role} gets the top bar and bottom navigation and no sideways scroll`, () => {
			cy.signInFresh(role);
			stubBell();
			stubToday();
			cy.bootOverride((boot) => {
				boot.company.name = "Pandya Realtors";
			});
			cy.visit("/sellos");
			cy.getByTestId("phone-topbar").should("be.visible");
			cy.getByTestId("phone-signout").should("be.visible");
			cy.getByTestId("phone-nav").should("be.visible");
			cy.getByTestId("phone-nav-home").should("be.visible");
			// SOS-P1-26: an agent and a sales manager land on Today. Let its lists finish loading.
			if (role === "agent" || role === "sales_manager") {
				todayLoaded();
				cy.getByTestId("today-counts", { timeout: 15000 }).should("be.visible");
			}
			if (BELL_ROLES.includes(role)) cy.wait("@notifications");
			cy.getByTestId("nav").should("not.be.visible");
			cy.getByTestId("signout").should("not.be.visible");
			cy.document().then((doc) => {
				const root = doc.documentElement;
				expect(root.scrollWidth, "page width").to.be.at.most(root.clientWidth);
			});
		});
	});

	it("an agent can use the bottom navigation and the phone sign out button", () => {
		cy.signInFresh("agent");
		stubBell();
		stubToday();
		cy.intercept("**/api/method/sellos.crm.api.list_leads*", { body: { message: [] } }).as(
			"leads"
		);
		// The leads screen also asks for its filter boxes. Stub and wait for them before signing out.
		cy.intercept("**/api/method/sellos.crm.api.lead_filter_options*", {
			body: { message: {} },
		}).as("filterOptions");
		cy.intercept("**/api/method/sellos.crm.api.list_stages*", { body: { message: [] } }).as(
			"stages"
		);
		cy.intercept("**/api/method/sellos.crm.api.list_lead_sources*", {
			body: { message: { sources: [] } },
		}).as("sources");
		cy.visit("/sellos");
		// SOS-P1-26: the agent lands on Today. Let its lists finish loading before leaving the page, so
		// no request is cut off in the middle.
		todayLoaded();
		cy.getByTestId("today-counts", { timeout: 15000 }).should("be.visible");
		cy.wait("@notifications");
		cy.getByTestId("phone-nav-leads").click();
		cy.location("pathname").should("eq", "/sellos/crm/leads");
		cy.wait(["@leads", "@filterOptions", "@stages"]);
		cy.wait(["@sources", "@sources"]);
		cy.intercept("POST", "**/api/method/logout").as("logout");
		cy.getByTestId("phone-signout").click();
		cy.wait("@logout");
		cy.location("pathname").should("eq", "/login");
	});

	it("shows the full side navigation again at desktop width", () => {
		cy.viewport(1280, 800);
		cy.signInFresh("agent");
		stubBell();
		stubToday();
		cy.visit("/sellos");
		todayLoaded();
		cy.getByTestId("today-counts", { timeout: 15000 }).should("be.visible");
		cy.wait("@notifications");
		cy.getByTestId("nav").should("be.visible");
		cy.getByTestId("phone-nav").should("not.be.visible");
	});
});
