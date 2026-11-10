// SOS-P1-13: a Company Admin gives support read access for a chosen time. It works, then it ends by
// itself, and every action is in the log. Goes through the real screen and the real server.
context("SOS-P1-13: support access grants", () => {
	// The grant and its log lines are committed, so remove them (SOS-SETUP-24).
	before(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_support_grants");
		cy.bench("sellos.tests.ui_fixtures.seed_agent_leads");
	});
	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_support_grants");
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});

	const leadsAsSupport = () =>
		cy
			.request({ url: "/api/resource/Lead?limit_page_length=50", failOnStatusCode: false })
			.then((res) => res);

	it("grants 1 hour of access, which works, then ends, and the log has the entries", () => {
		cy.signInFresh("platform_admin");
		leadsAsSupport().then((res) => {
			expect(res.body.data || [], "no grant, no leads").to.have.length(0);
		});

		cy.signInFresh("company_admin");
		cy.visit("/sellos/company/support");
		cy.getByTestId("support-empty").should("be.visible");
		cy.getByTestId("support-duration").select("1 hour");
		cy.getByTestId("support-reason").type("Help with the leads list");
		cy.getByTestId("support-grant").click();
		cy.getByTestId("support-error").should("not.exist");
		cy.getByTestId("support-grant-row").should("have.length", 1);
		cy.getByTestId("support-status").should("contain.text", "Active");

		// Support signs in and reads.
		cy.signInFresh("platform_admin");
		leadsAsSupport().then((res) => {
			expect(res.status).to.eq(200);
			expect(res.body.data.length, "support reads the company's leads").to.be.greaterThan(0);
		});

		// An hour passes.
		cy.bench("sellos.tests.ui_fixtures.end_support_grant_now");
		leadsAsSupport().then((res) => {
			expect(res.body.data || [], "access ended at expiry").to.have.length(0);
		});

		// The Company Admin sees it ended, and the log of who did what, and when.
		cy.signInFresh("company_admin");
		cy.visit("/sellos/company/support");
		cy.getByTestId("support-status").should("contain.text", "Expired");
		cy.getByTestId("support-show-log").click();
		cy.getByTestId("support-log-row").should("have.length.greaterThan", 2);
		cy.getByTestId("support-log").should("contain.text", "Granted");
		cy.getByTestId("support-log").should("contain.text", "Request");
		cy.getByTestId("support-log").should("contain.text", "GET /api/resource/Lead");
		cy.getByTestId("support-log")
			.invoke("text")
			.should("match", /\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/);
	});

	it("the company admin can end access early, and other roles have no such page", () => {
		cy.signInFresh("company_admin");
		cy.visit("/sellos/company/support");
		cy.getByTestId("support-grant").click();
		cy.getByTestId("support-revoke").click();
		cy.getByTestId("support-status").first().should("contain.text", "Revoked");

		cy.signInFresh("platform_admin");
		leadsAsSupport().then((res) => {
			expect(res.body.data || [], "ended by the admin").to.have.length(0);
		});

		["agent", "client", "channel_partner", "platform_admin"].forEach((role) => {
			cy.signInFresh(role);
			cy.visit("/sellos/company/support");
			cy.getByTestId("no-access").should("be.visible");
			cy.getByTestId("support-grant").should("not.exist");
		});
	});
});
