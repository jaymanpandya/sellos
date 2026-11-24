// SOS-P0-10: which routes each role may open. Replaces router.test.js and the route half of
// crm.test.js. A route that is refused shows the no access page; one that is allowed shows its own.
const LEAD = {
	message: {
		lead: { name: "LD-1" },
		client: { client_name: "Asha Rao", client_type: "Buyer", phone: "*********345" },
		timeline: [],
	},
};

context("SOS-P0-10: route access", () => {
	// SOS-SETUP-38: the leads screen asks for the lead sources whenever its user may make a lead
	// (SOS-P1-20). That call was the only one this spec did not stub, so a test ended with it still
	// running, the next test's visit cut it off, and on a slow CI runner the app logged "list_lead_sources
	// failed Failed to fetch" after its leaving-the-page mark had lapsed (CI runs 43897848128,
	// 43902088789 and 43954312044). Every call the screens make is stubbed, and a test that opens the
	// leads screen as a user who may make a lead waits for the sources before it moves on.
	const stubCrm = () => {
		cy.intercept("**/api/method/sellos.crm.api.list_leads*", { body: { message: [] } });
		cy.intercept("**/api/method/sellos.crm.api.get_lead*", { body: LEAD });
		cy.intercept("**/api/method/sellos.crm.api.list_lead_sources*", {
			body: { message: { sources: [], can_manage: false } },
		}).as("sources");
		// The leads screen also asks for its filter lists and the stages (SOS-P1-25 added a nav link,
		// and a test that ends while these are in flight logs "lead_filter_options failed").
		cy.intercept("**/api/method/sellos.crm.api.lead_filter_options*", {
			body: { message: {} },
		});
		cy.intercept("**/api/method/sellos.crm.api.list_stages*", { body: { message: [] } });
		// The lead page (LD-1 does not exist) also asks for its booking panel (SOS-P7-10). Unstubbed, the
		// server answered 404 whenever the answer landed inside a later test, which failed that test's
		// check for unexpected API failures. stubBookingPanel is the stub every lead page spec uses.
		cy.stubBookingPanel();
	};

	it("sends a user without a SellOS role to the no access page", () => {
		cy.signInFresh("basic");
		cy.visit("/sellos");
		cy.getByTestId("no-access").should("be.visible");
	});

	["platform_admin", "company_admin", "agent", "channel_partner", "client"].forEach((role) => {
		it(`lets ${role} open the home page`, () => {
			cy.signInFresh(role);
			cy.visit("/sellos");
			cy.getByTestId("home").should("be.visible");
			cy.getByTestId("no-access").should("not.exist");
			// An agent lands on Today: let its lists load, so the next test cuts no request off.
			if (role === "agent")
				cy.getByTestId("today-counts", { timeout: 15000 }).should("be.visible");
		});
	});

	it("always lets a user reach the no access page itself", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos/no-access");
		cy.getByTestId("no-access").should("be.visible");
		cy.signInFresh("basic");
		cy.visit("/sellos/no-access");
		cy.getByTestId("no-access").should("be.visible");
	});

	it("lets agents and company admins open the leads", () => {
		stubCrm();
		cy.signInFresh("agent");
		cy.visit("/sellos/crm/leads");
		cy.getByTestId("leads-page").should("be.visible");
		cy.wait("@sources");
		cy.signInFresh("company_admin");
		cy.visit("/sellos/crm/leads/LD-1");
		cy.getByTestId("lead-page").should("be.visible");
		cy.wait("@sources");
	});

	it("keeps partners, clients and the platform admin out of the CRM area", () => {
		stubCrm();
		["channel_partner", "client", "platform_admin"].forEach((role) => {
			cy.signInFresh(role);
			cy.visit("/sellos/crm/leads");
			cy.getByTestId("no-access").should("be.visible");
			cy.getByTestId("leads-page").should("not.exist");
		});
	});

	it("gives partners their own leads route and nobody else", () => {
		stubCrm();
		cy.signInFresh("channel_partner");
		cy.visit("/sellos/partner/leads");
		cy.getByTestId("leads-page").should("be.visible");
		["agent", "client"].forEach((role) => {
			cy.signInFresh(role);
			cy.visit("/sellos/partner/leads");
			cy.getByTestId("no-access").should("be.visible");
		});
	});
});
