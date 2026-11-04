// SOS-P1-06A (reopened from SOS-P1-06): the leads list and the new lead form. Replaces the leads page half of crm.test.js.
// The server's answers are stubbed, as the old tests stubbed crmApi, so these check the screen
// and what it asks the server to do. cypress/integration/crm/leads_by_role.cy.js uses the real server.
const LEAD = {
	message: {
		lead: { name: "LD-1" },
		client: { client_name: "Asha Rao", client_type: "Buyer", phone: "*********345" },
		timeline: [],
	},
};

context("SOS-P1-06A: leads screen", () => {
	it("lists leads and shows overdue tasks", () => {
		cy.signInFresh("agent");
		cy.intercept("**/api/method/sellos.crm.api.list_leads*", {
			body: {
				message: [
					{ name: "LD-1", client_name: "Asha Rao", source: "Website", overdue_tasks: 2 },
				],
			},
		});
		cy.visit("/sellos/crm/leads");
		cy.getByTestId("lead-row").should("contain", "Asha Rao");
		cy.getByTestId("lead-overdue").should("contain", "2 overdue");
	});

	it("creates a client and a lead, then opens the lead", () => {
		cy.signInFresh("agent");
		cy.intercept("**/api/method/sellos.crm.api.list_leads*", { body: { message: [] } });
		cy.intercept("**/api/method/sellos.crm.api.save_client*", {
			body: { message: { name: "CL-1" } },
		}).as("saveClient");
		cy.intercept("**/api/method/sellos.crm.api.save_lead*", {
			body: { message: { lead: { name: "LD-1" } } },
		}).as("saveLead");
		cy.intercept("**/api/method/sellos.crm.api.get_lead*", { body: LEAD });
		cy.visit("/sellos/crm/leads");
		cy.getByTestId("leads-new").click();
		cy.getByTestId("lead-form-name").type("Asha Rao");
		cy.getByTestId("lead-form-source").type("Website");
		cy.getByTestId("lead-form").submit();
		cy.wait("@saveClient")
			.its("request.body")
			.then((body) => cy.bodyOf(body))
			.then((sent) => {
				expect(sent.values.client_name).to.eq("Asha Rao");
				expect(sent.values.client_type).to.eq("Buyer");
			});
		cy.wait("@saveLead")
			.its("request.body")
			.then((body) => cy.bodyOf(body))
			.then((sent) => {
				expect(sent.values).to.deep.equal({ client: "CL-1", source: "Website" });
			});
		cy.location("pathname").should("eq", "/sellos/crm/leads/LD-1");
	});
});
