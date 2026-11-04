// SOS-P1-06: one lead, its timeline and what each role may do on it. Replaces the lead page half of
// crm.test.js. The server's answers are stubbed, as the old tests stubbed crmApi.
const lead = (timeline = []) => ({
	message: {
		lead: { name: "LD-1" },
		client: { client_name: "Asha Rao", client_type: "Buyer", phone: "*********345" },
		timeline,
	},
});

context("SOS-P1-06: lead detail", () => {
	it("logs an activity and reloads the timeline", () => {
		cy.signInFresh("agent");
		let loads = 0;
		cy.intercept("**/api/method/sellos.crm.api.get_lead*", (req) => {
			loads += 1;
			req.reply({
				body: lead(
					loads === 1
						? []
						: [
								{
									kind: "activity",
									name: "A1",
									title: "Call",
									when: "2026-11-04 10:00:00",
									notes: "intro",
								},
						  ]
				),
			});
		});
		cy.intercept("**/api/method/sellos.crm.api.add_activity*", { body: { message: {} } }).as(
			"addActivity"
		);
		cy.visit("/sellos/crm/leads/LD-1");
		cy.getByTestId("lead-phone").should("contain", "*********345");
		cy.getByTestId("lead-timeline-empty").should("contain", "Nothing logged yet");
		cy.getByTestId("lead-activity-notes").type("intro");
		cy.getByTestId("lead-activity-form").submit();
		cy.wait("@addActivity")
			.its("request.body")
			.then((body) => cy.bodyOf(body))
			.then((sent) => {
				expect(sent.lead).to.eq("LD-1");
				expect(sent.activity_type).to.eq("Call");
				expect(sent.notes).to.eq("intro");
			});
		cy.getByTestId("lead-timeline-item").should("contain", "intro");
	});

	it("marks an overdue task", () => {
		cy.signInFresh("agent");
		cy.intercept("**/api/method/sellos.crm.api.get_lead*", {
			body: lead([
				{
					kind: "task",
					name: "T1",
					title: "Send brochure",
					when: "2026-11-01",
					status: "Open",
					overdue: true,
				},
			]),
		});
		cy.visit("/sellos/crm/leads/LD-1");
		cy.getByTestId("lead-timeline-overdue").should("contain", "Overdue");
	});

	it("shows a partner the timeline but no way to log or archive", () => {
		cy.signInFresh("channel_partner");
		cy.intercept("**/api/method/sellos.crm.api.get_lead*", {
			body: lead([
				{ kind: "activity", name: "A1", title: "Call", when: "2026-11-04 10:00:00" },
			]),
		});
		cy.visit("/sellos/partner/leads/LD-1");
		cy.getByTestId("lead-timeline-item").should("contain", "Call");
		cy.getByTestId("lead-activity-form").should("not.exist");
		cy.getByTestId("lead-archive").should("not.exist");
	});
});
