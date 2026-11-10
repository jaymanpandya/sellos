// SOS-P0-10: the layout works at phone width (390 px wide). The side navigation gives way to a top bar
// and a bottom navigation, and nothing scrolls sideways.
const ROLES = ["platform_admin", "company_admin", "agent", "channel_partner", "client"];

context("SOS-P0-10: phone layout", () => {
	beforeEach(() => {
		cy.viewport(390, 844);
	});

	ROLES.forEach((role) => {
		it(`${role} gets the top bar and bottom navigation and no sideways scroll`, () => {
			cy.signInFresh(role);
			cy.bootOverride((boot) => {
				boot.company.name = "Pandya Realtors";
			});
			cy.visit("/sellos");
			cy.getByTestId("phone-topbar").should("be.visible");
			cy.getByTestId("phone-signout").should("be.visible");
			cy.getByTestId("phone-nav").should("be.visible");
			cy.getByTestId("phone-nav-home").should("be.visible");
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
		cy.intercept("**/api/method/sellos.crm.api.list_leads*", { body: { message: [] } });
		cy.visit("/sellos");
		cy.getByTestId("phone-nav-leads").click();
		cy.location("pathname").should("eq", "/sellos/crm/leads");
		cy.intercept("POST", "**/api/method/logout").as("logout");
		cy.getByTestId("phone-signout").click();
		cy.wait("@logout");
		cy.location("pathname").should("eq", "/login");
	});

	it("shows the full side navigation again at desktop width", () => {
		cy.viewport(1280, 800);
		cy.signInFresh("agent");
		cy.visit("/sellos");
		cy.getByTestId("nav").should("be.visible");
		cy.getByTestId("phone-nav").should("not.be.visible");
	});
});
