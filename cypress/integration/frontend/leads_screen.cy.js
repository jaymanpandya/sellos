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

// The screen also asks for the filter boxes, the stages and the sources (SOS-P1-24). They are stubbed
// too, so no request is left in flight when the test moves to another page.
function stubFilterBoxes() {
	cy.intercept("**/api/method/sellos.crm.api.lead_filter_options*", {
		body: { message: { agents: [], teams: [], consent_statuses: [], untouched_days: 7 } },
	});
	cy.intercept("**/api/method/sellos.crm.api.list_stages*", { body: { message: [] } });
	cy.intercept("**/api/method/sellos.crm.api.list_lead_sources*", {
		body: { message: { sources: [{ name: "Website" }], can_manage: false } },
	});
}

context("SOS-P1-06A: leads screen", () => {
	it("lists leads and shows overdue tasks", () => {
		cy.signInFresh("agent");
		stubFilterBoxes();
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
		stubFilterBoxes();
		cy.intercept("**/api/method/sellos.crm.api.list_leads*", { body: { message: [] } });
		cy.intercept("**/api/method/sellos.crm.api.save_client*", {
			body: { message: { name: "CL-1" } },
		}).as("saveClient");
		cy.intercept("**/api/method/sellos.crm.api.save_lead*", {
			body: { message: { lead: { name: "LD-1" } } },
		}).as("saveLead");
		cy.intercept("**/api/method/sellos.crm.api.get_lead*", { body: LEAD });
		cy.visit("/sellos/crm/leads");
		cy.fillNewLead({ name: "Asha Rao", source: "Website" });
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

	// The newest request wins. The first, unfiltered answer is held back until after the filtered one
	// has been drawn; it must not put the unfiltered list back on the screen.
	it("a slow earlier answer does not overwrite the filtered list", () => {
		cy.signInFresh("agent");
		stubFilterBoxes();
		const everyone = [
			{ name: "LD-1", client_name: "Asha Rao", source: "Website", overdue_tasks: 0 },
			{ name: "LD-2", client_name: "Vikram Shah", source: "Website", overdue_tasks: 0 },
		];
		const filtered = [everyone[0]];
		cy.intercept("**/api/method/sellos.crm.api.list_leads*", (req) => {
			const searched = JSON.stringify(req.body || "").includes("Asha");
			req.reply({
				body: { message: searched ? filtered : everyone },
				delay: searched ? 0 : 2500,
			});
		}).as("listLeads");
		cy.visit("/sellos/crm/leads");
		cy.getByTestId("leads-search").type("Asha");
		cy.getByTestId("lead-row").should("have.length", 1).and("contain", "Asha Rao");
		// Both answers have arrived once the second request has completed and the delay has passed.
		cy.wait("@listLeads");
		cy.wait("@listLeads");
		cy.wait(3000);
		cy.getByTestId("lead-row").should("have.length", 1).and("contain", "Asha Rao");
		cy.getByTestId("lead-row").should("not.contain", "Vikram Shah");
	});
});
