// Every role gets in, lands in the web app, and only the platform admin reaches the Frappe desk.
// Nothing here needs data. It is the first spec to read when the app does not load.
context("SOS-P0-10: app shell and access by role", () => {
	const roles = ["platform_admin", "company_admin", "agent", "channel_partner", "client"];

	it("sends a signed out visitor to the login page and back after sign in", () => {
		cy.visit("/login");
		cy.signOut();
		cy.visit("/sellos");
		cy.location("pathname").should("eq", "/login");
		cy.location("search").should("contain", "redirect-to=/sellos");
	});

	roles.forEach((role) => {
		it(`${role} reaches the web app and can sign out`, () => {
			cy.signInFresh(role);
			cy.visit("/sellos");
			cy.getByTestId("app-shell").should("be.visible");
			cy.getByTestId("nav-home").should("be.visible");
			cy.signOut();
		});

		it(`${role} ${role === "platform_admin" ? "can" : "cannot"} open the Frappe desk`, () => {
			cy.signInFresh(role);
			cy.request({ url: "/desk/user", followRedirect: false, failOnStatusCode: false }).then(
				(res) => {
					if (role === "platform_admin") {
						expect(res.status, "desk for the platform admin").to.eq(200);
					} else {
						expect(res.status, "desk for a customer role").to.not.eq(200);
					}
				}
			);
		});
	});

	it("a user with no SellOS role is told there is nothing for them", () => {
		cy.signInFresh("basic");
		cy.visit("/sellos");
		cy.getByTestId("no-access").should("be.visible");
	});
});
