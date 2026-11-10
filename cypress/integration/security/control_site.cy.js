// SOS-P1-01: the control site. A Platform Admin creates companies and moves them through the allowed
// statuses, and company users can not open it. Goes through the real screen and the real server.
context("SOS-P1-01: the control site", () => {
	// Tenants are committed records the app never deletes, so remove them (SOS-SETUP-24).
	before(() => cy.bench("sellos.tests.ui_fixtures.remove_control_records"));
	after(() => cy.bench("sellos.tests.ui_fixtures.remove_control_records"));

	it("a Platform Admin creates a company and moves it through the allowed order", () => {
		cy.signInFresh("platform_admin");
		cy.visit("/sellos/control/tenants");
		cy.getByTestId("tenant-empty").should("be.visible");
		cy.getByTestId("tenant-id").type("cyacme");
		cy.getByTestId("tenant-company").type("Cypress Acme Realty");
		cy.getByTestId("tenant-email").type("owner@example.com");
		cy.getByTestId("tenant-create").click();
		cy.getByTestId("tenant-error").should("not.exist");
		cy.getByTestId("tenant-row").should("have.length", 1);
		cy.getByTestId("tenant-status").should("contain.text", "Requested");
		cy.getByTestId("tenant-row").should("contain.text", "sellos_tenant_cyacme.localhost");
		// Only the next step is offered.
		cy.getByTestId("tenant-to-active").should("not.exist");
		cy.getByTestId("tenant-to-provisioning").click();
		cy.getByTestId("tenant-status").should("contain.text", "Provisioning");
		cy.getByTestId("tenant-to-active").click();
		cy.getByTestId("tenant-status").should("contain.text", "Active");
		cy.getByTestId("tenant-to-provisioning").should("not.exist");
		cy.getByTestId("tenant-to-failed").should("not.exist");
	});

	it("refuses an unsafe tenant ID with a clear message", () => {
		cy.expectApiStatus("frappe.client.insert", 417);
		cy.signInFresh("platform_admin");
		cy.visit("/sellos/control/tenants");
		cy.getByTestId("tenant-id").invoke("removeAttr", "pattern");
		cy.getByTestId("tenant-id").type("Bad Id");
		cy.getByTestId("tenant-company").type("Bad Realty");
		cy.getByTestId("tenant-email").type("bad@example.com");
		cy.getByTestId("tenant-create").click();
		cy.getByTestId("tenant-error").should("contain.text", "lower case letters and digits");
	});

	["company_admin", "agent", "channel_partner", "client"].forEach((role) => {
		it(`${role} gets the no access page and no company`, () => {
			cy.signInFresh(role);
			cy.visit("/sellos/control/tenants");
			cy.getByTestId("no-access").should("be.visible");
			cy.getByTestId("tenant-row").should("not.exist");
			cy.getByTestId("nav").should("not.contain.text", "Companies");
		});
	});

	it("a company admin's direct request for the companies is refused", () => {
		cy.signInFresh("company_admin");
		cy.request({
			url: "/api/resource/Tenant?limit_page_length=50",
			failOnStatusCode: false,
		}).then((res) => {
			expect(res.status).to.be.oneOf([401, 403]);
			expect(JSON.stringify(res.body)).not.to.contain("cyacme");
		});
	});
});
