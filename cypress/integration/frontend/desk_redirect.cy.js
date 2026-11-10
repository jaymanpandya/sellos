// SOS-P0-10: customer roles are redirected away from the desk to the web app. Only the platform admin
// may open it. Both /desk and /app are checked, because /app is the older address of the desk.
const CUSTOMER_ROLES = ["company_admin", "agent", "channel_partner", "client", "basic"];

context("SOS-P0-10: the desk is blocked for customer roles", () => {
	CUSTOMER_ROLES.forEach((role) => {
		["/desk", "/desk/user", "/app", "/app/user"].forEach((path) => {
			it(`${role} is sent from ${path} to the web app`, () => {
				cy.signInFresh(role);
				cy.request({ url: path, followRedirect: false, failOnStatusCode: false }).then(
					(res) => {
						expect(res.status).to.eq(302);
						expect(res.redirectedToUrl || res.headers.location).to.match(/\/sellos$/);
					}
				);
			});
		});

		it(`${role} who types /desk ends up in the web app, not the desk`, () => {
			cy.signInFresh(role);
			cy.visit("/desk");
			cy.location("pathname").should("match", /^\/sellos/);
			cy.getByTestId("app-shell").should("be.visible");
		});
	});

	it("the platform admin may still open the desk", () => {
		cy.signInFresh("platform_admin");
		cy.request({ url: "/desk/user", followRedirect: false, failOnStatusCode: false })
			.its("status")
			.should("eq", 200);
	});
});
