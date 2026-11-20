// SOS-P2-10: calling hours are a company setting and a do not call list flags leads. The Company Admin saves
// a calling window that is closed right now and an agent's call is refused with the hours in the message; the
// Company Admin imports a do not call list and the listed lead shows an amber Registered DND warning, in the
// caller queue too, and the call proceeds. Real screens, real server, the fake provider.
context("SOS-P2-10: calling hours and the do not call list", () => {
	let seed;

	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_calling_rules").then((made) => {
			seed = made;
		});
	});
	afterEach(() => {
		cy.visit("/sellos/crm/leads");
		cy.bench("sellos.tests.ui_fixtures.remove_calling_rules");
	});

	it("refuses a call outside the calling hours with the hours in the message", () => {
		cy.signInFresh("company_admin");
		cy.visit("/sellos/company/telephony");
		cy.getByTestId("calling-hours-enabled").check();
		cy.getByTestId("calling-hours-start").clear().type(seed.closed_start);
		cy.getByTestId("calling-hours-end").clear().type(seed.closed_end);
		cy.getByTestId("calling-hours-save").click();
		cy.getByTestId("calling-hours-saved").should("contain", "India time");

		cy.signInFresh("agent");
		cy.visit(`/sellos/crm/leads/${seed.leads.unknown}`);
		cy.getByTestId("click-to-call").click();
		cy.getByTestId("call-error")
			.should("contain", "India time")
			.and("contain", "Calls can only be placed");
		cy.getByTestId("call-start").should("be.disabled");
	});

	it("flags a listed lead Registered DND with an amber warning and still lets the agent call", () => {
		cy.signInFresh("company_admin");
		cy.visit("/sellos/company/telephony");
		cy.get('textarea[data-testid="sellos-dnd-text"]').type(
			`number\n${seed.dnd_number}\nnot a number`
		);
		cy.getByTestId("dnd-import").click();
		cy.getByTestId("dnd-result")
			.should("contain", "1 added")
			.and("contain", "1 skipped")
			.and("contain", "1 leads marked Registered DND");

		cy.signInFresh("agent");
		cy.visit("/sellos/crm/queue");
		cy.contains("Registered DND").should("be.visible");
		cy.visit(`/sellos/crm/leads/${seed.leads.unknown}`);
		cy.getByTestId("click-to-call").click();
		cy.getByTestId("call-consent").should("have.attr", "data-level", "amber");
		cy.getByTestId("call-warning").should("contain", "do not call");
		cy.getByTestId("call-start").should("not.be.disabled").click();
		cy.getByTestId("call-stage").should("have.attr", "data-stage", "agent_ringing");
		cy.getByTestId("call-warning").should("be.visible");
	});
});
