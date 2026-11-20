// SOS-P2-07: click to call, against the real server and the fake provider. ui_fixtures.seed_click_to_call
// turns the fake provider on, saves the Plivo account with fake keys, gives the test agent an Indian mobile
// number and makes the caller queue's six leads (Soon, Months, Forever, Unknown, Opted out and Dnd).
// play_click_to_call plays the provider's side of the call: the agent answers, the lead answers, hangup.
// remove_click_to_call removes it all afterwards. No call leaves the machine.
context("SOS-P2-07: click to call", () => {
	let seed;

	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_click_to_call").then((made) => {
			seed = made;
		});
	});
	afterEach(() => {
		// Leave the page first, so the open dialog stops reading a call the fixture is about to remove.
		cy.visit("/sellos/crm/leads");
		cy.bench("sellos.tests.ui_fixtures.remove_click_to_call");
	});

	const openLead = (key) => {
		cy.signInFresh("agent");
		cy.visit(`/sellos/crm/leads/${seed.leads[key]}`);
		cy.getByTestId("lead-page").should("be.visible");
		cy.getByTestId("click-to-call").click();
		cy.getByTestId("call-dialog").should("be.visible");
	};
	const play = (step) => cy.bench("sellos.tests.ui_fixtures.play_click_to_call", { step });

	it("shows the amber warning before the call, calls anyway, and keeps the warning during it", () => {
		openLead("unknown");
		cy.getByTestId("call-consent").should("have.attr", "data-level", "amber");
		cy.getByTestId("call-warning").should("be.visible");
		cy.getByTestId("call-start").should("not.be.disabled").click();
		cy.getByTestId("call-stage").should("have.attr", "data-stage", "agent_ringing");
		cy.getByTestId("call-warning").should("be.visible");
		play("agent_answers");
		cy.getByTestId("call-stage").should("have.attr", "data-stage", "connecting");
		play("lead_answers");
		cy.getByTestId("call-stage").should("have.attr", "data-stage", "connected");
		cy.getByTestId("call-consent").should("have.attr", "data-level", "amber");
	});

	it("shows a red warning for an opted out lead and still lets the agent call", () => {
		openLead("opted");
		cy.getByTestId("call-consent").should("have.attr", "data-level", "red");
		cy.getByTestId("call-warning").should("be.visible");
		cy.getByTestId("call-start").should("not.be.disabled");
	});

	it("shows no warning for a consented lead", () => {
		openLead("forever");
		cy.getByTestId("call-consent").should("have.attr", "data-level", "none");
		cy.getByTestId("call-warning").should("not.exist");
	});

	it("asks for the outcome after hangup and will not close until it is saved", () => {
		openLead("unknown");
		cy.getByTestId("call-start").click();
		cy.getByTestId("call-stage").should("have.attr", "data-stage", "agent_ringing");
		play("agent_answers");
		play("lead_answers");
		play("hangup");
		cy.getByTestId("call-outcome-form").should("be.visible");
		// An outcome is required: saving with none is refused and the form stays.
		cy.intercept("POST", "**/api/method/sellos.telephony.click_to_call.record_outcome*").as(
			"outcome"
		);
		cy.getByTestId("call-outcome-save").click();
		cy.getByTestId("call-error").should("contain", "Choose an outcome");
		cy.getByTestId("call-outcome-form").should("be.visible");
		cy.get("body").type("{esc}");
		cy.getByTestId("call-outcome-form").should("be.visible");
		cy.getByTestId("call-outcome").select("Wrong number");
		cy.getByTestId("call-notes").type("Spoke for 42 seconds");
		cy.getByTestId("call-outcome-save").click();
		cy.wait("@outcome").its("response.statusCode").should("eq", 200);
		cy.getByTestId("call-dialog").should("not.exist");
		cy.getByTestId("lead-timeline-outcome")
			.closest("[data-testid=sellos-lead-timeline-item]")
			.should("contain", "Wrong number")
			.and("contain", "Spoke for 42 seconds");
	});

	it("asks for the outcome again when the page is opened with a finished call that has none", () => {
		openLead("unknown");
		cy.getByTestId("call-start").click();
		play("agent_answers");
		play("lead_answers");
		play("hangup");
		cy.getByTestId("call-outcome-form").should("be.visible");
		cy.reload();
		cy.getByTestId("call-outcome-form").should("be.visible");
	});

	it("shows a clear error for an agent number outside India and places no call", () => {
		cy.bench("sellos.tests.ui_fixtures.set_click_to_call_agent_mobile", { abroad: 1 });
		openLead("unknown");
		cy.getByTestId("call-error").should("contain", "not an Indian number");
		cy.getByTestId("call-start").should("be.disabled");
	});
});
