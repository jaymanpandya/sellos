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
	const stubCrm = () => {
		cy.intercept("**/api/method/sellos.crm.api.list_leads*", { body: { message: [] } });
		cy.intercept("**/api/method/sellos.crm.api.get_lead*", { body: LEAD });
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
		cy.signInFresh("company_admin");
		cy.visit("/sellos/crm/leads/LD-1");
		cy.getByTestId("lead-page").should("be.visible");
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
