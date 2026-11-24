// SOS-P1-21: logging a call by hand, the follow up an outcome needs, the suggested stage and the lost
// reason, against the real server. The leads come from sellos.crm.api through seed_consent_leads (one
// for each consent status) and are removed afterwards, with the outcome and reason the spec adds
// (SOS-SETUP-24). Every lead is opened by the agent who owns it.
context("SOS-P1-21: call outcomes and logging a call by hand", () => {
	let leads;
	const tag = Date.now();

	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_consent_leads").then((made) => {
			leads = made;
		});
	});

	afterEach(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
		cy.bench("sellos.tests.ui_fixtures.remove_gate_call_lists");
	});

	const open = (status) => {
		cy.signInFresh("agent");
		cy.visit(`/sellos/crm/leads/${leads[status]}?tab=calls`);
		cy.getByTestId("lead-summary-stage").should("have.attr", "data-stage", "New");
	};

	// Click Log call and wait until the form has taken the answer and cleared itself, so the next
	// step never types into a form that is about to be reset.
	const logCall = () => {
		cy.intercept("POST", "**/api/method/sellos.crm.api.log_call*").as("logCall");
		cy.getByTestId("lead-call-save").click();
		cy.wait("@logCall").its("response.statusCode").should("eq", 200);
		cy.getByTestId("lead-call-saved").should("be.visible");
		cy.getByTestId("lead-call-outcome").should("have.value", "");
	};

	it("lists the seven outcomes the Company Admin keeps", () => {
		open("Consented");
		cy.optionTexts("lead-call-outcome").then((texts) => {
			expect(texts).to.deep.eq([
				"Outcome",
				"Interested",
				"Call back later",
				"Not reachable",
				"Busy",
				"Wrong number",
				"Not interested",
				"Site visit booked",
			]);
		});
	});

	["Consented", "Unknown", "Opted out", "Registered DND"].forEach((status) => {
		it(`logs a call with a follow up on a ${status} lead`, () => {
			open(status);
			cy.getByTestId("lead-call-follow-up").should("not.exist");
			cy.getByTestId("lead-call-outcome").select("Call back later");
			cy.getByTestId("lead-call-minutes").type("3");
			cy.getByTestId("lead-call-notes").type("Ring after lunch");
			// The outcome needs a follow up, so the form asks for its date and time.
			cy.getByTestId("lead-call-follow-up")
				.should("be.visible")
				.and("have.attr", "required");
			cy.getByTestId("lead-call-follow-up").type("2030-03-04T10:30");
			logCall();
			cy.getByTestId("lead-call-saved").should("contain", "follow up set");
			cy.getByTestId("lead-timeline-outcome")
				.closest("[data-testid=sellos-lead-timeline-item]")
				.should("contain", "Call back later")
				.and("contain", "3 min")
				.and("contain", "Ring after lunch");
			cy.getByTestId("lead-timeline-item")
				.contains("Follow up: Call back later")
				.closest("[data-testid=sellos-lead-timeline-item]")
				.should("contain", "4 Mar 2030, 10:30");
			// Logging a call never moves the lead for the agent.
			cy.getByTestId("lead-summary-stage").should("have.attr", "data-stage", "New");
		});
	});

	it("will not log an outcome that needs a follow up without its date", () => {
		open("Unknown");
		cy.getByTestId("lead-call-outcome").select("Busy");
		cy.getByTestId("lead-call-follow-up").should("be.visible");
		cy.intercept("POST", "**/api/method/sellos.crm.api.log_call*", cy.spy().as("logCallSpy"));
		cy.getByTestId("lead-call-save").click();
		cy.get("@logCallSpy").should("not.have.been.called");
		cy.getByTestId("lead-timeline-item").should("not.exist");
	});

	it("offers the suggested stage, and the agent picks it or any other stage", () => {
		open("Opted out");
		cy.getByTestId("lead-call-outcome").select("Site visit booked");
		cy.getByTestId("lead-call-suggestion")
			.should("be.visible")
			.and("contain", "Suggested stage: Site visit booked");
		cy.getByTestId("lead-call-stage").should("contain", "Keep the stage");
		logCall();
		// Offered, not forced: the lead is still on New.
		cy.getByTestId("lead-summary-stage").should("have.attr", "data-stage", "New");

		cy.getByTestId("lead-call-outcome").select("Site visit booked");
		cy.getByTestId("lead-call-suggestion").click();
		cy.getByTestId("lead-call-stage").should("contain", "Site visit booked");
		logCall();
		cy.getByTestId("lead-summary-stage").should(
			"have.attr",
			"data-stage",
			"Site visit booked"
		);

		// Any other stage may be picked instead of the suggestion.
		cy.getByTestId("lead-call-outcome").select("Site visit booked");
		cy.getByTestId("lead-call-stage").select("Negotiation");
		logCall();
		cy.getByTestId("lead-summary-stage").should("have.attr", "data-stage", "Negotiation");
	});

	it("asks for a lost reason when a call moves the lead to Closed lost", () => {
		open("Registered DND");
		cy.getByTestId("lead-call-outcome").select("Not interested");
		cy.getByTestId("lead-call-suggestion").should("contain", "Closed lost").click();
		// A frappe-ui select has no native required attribute; the field's label carries the red star.
		cy.getByTestId("lead-call-lost-reason").should("be.visible");
		cy.getByTestId("lead-call-lost-reason")
			.parents("div.space-y-1\\.5")
			.first()
			.should("contain", "*");
		cy.getByTestId("lead-call-lost-reason").select("Bought elsewhere");
		logCall();
		cy.getByTestId("lead-summary-stage").should("have.attr", "data-stage", "Closed lost");
		cy.getByTestId("tab-overview").click();
		cy.getByTestId("lead-lost-reason-shown").should("contain", "Bought elsewhere");
		cy.getByTestId("lead-stage-change-reason").first().should("contain", "Bought elsewhere");
	});

	it("asks for a lost reason when the stage box moves a lead to Closed lost", () => {
		open("Unknown");
		cy.intercept("POST", "**/api/method/sellos.crm.api.move_lead_stage*").as("move");
		cy.getByTestId("tab-overview").click();
		cy.getByTestId("lead-stage-select").select("Closed lost");
		cy.getByTestId("lead-lost-form").should("be.visible");
		cy.getByTestId("lead-summary-stage").should("have.attr", "data-stage", "New");
		// Cancel puts the box back on the lead's own stage and moves nothing.
		cy.getByTestId("lead-lost-cancel").click();
		cy.getByTestId("lead-lost-form").should("not.exist");
		cy.getByTestId("lead-stage-select").should("have.value", "New");

		cy.getByTestId("lead-stage-select").select("Closed lost");
		cy.optionTexts("lead-lost-reason").should("include", "Budget too low");
		cy.getByTestId("lead-lost-reason").select("Budget too low");
		cy.getByTestId("lead-lost-save").click();
		cy.wait("@move").its("response.statusCode").should("eq", 200);
		cy.getByTestId("lead-summary-stage").should("have.attr", "data-stage", "Closed lost");
		cy.getByTestId("lead-lost-reason-shown").should("contain", "Budget too low");
	});

	it("a company admin adds an outcome and a lost reason and the agent picks them", () => {
		const outcome = `Gate Outcome ${tag}`;
		const reason = `Gate Reason ${tag}`;
		cy.signInFresh("company_admin");
		cy.visit("/sellos/company/call-lists");
		cy.getByTestId("calllists-outcome").should("have.length.at.least", 7);
		cy.intercept("POST", "**/api/method/sellos.crm.api.save_call_outcome*").as("saveOutcome");
		cy.intercept("POST", "**/api/method/sellos.crm.api.save_lost_reason*").as("saveReason");
		// The add forms are drawers, opened from the page header.
		cy.getByTestId("calllists-new-outcome-open").click();
		cy.getByTestId("calllists-new-outcome").type(outcome);
		cy.getByTestId("calllists-new-outcome-followup").check();
		cy.getByTestId("calllists-new-outcome-stage").select("Contacted");
		cy.getByTestId("calllists-add-outcome").click();
		cy.wait("@saveOutcome").its("response.statusCode").should("eq", 200);
		cy.getByTestId("calllists-outcome")
			.filter(`[data-name="${outcome}"]`)
			.should("have.length", 1)
			.find("[data-testid=sellos-calllists-outcome-stage]")
			.should("have.value", "Contacted");
		cy.getByTestId("calllists-new-reason-open").click();
		cy.getByTestId("calllists-new-reason").type(reason);
		cy.getByTestId("calllists-add-reason").click();
		cy.wait("@saveReason").its("response.statusCode").should("eq", 200);
		cy.getByTestId("calllists-reason")
			.filter(`[data-name="${reason}"]`)
			.should("have.length", 1);

		cy.signInFresh("agent");
		cy.visit(`/sellos/crm/leads/${leads.Unknown}?tab=calls`);
		cy.optionTexts("lead-call-outcome").should("include", outcome);
		cy.getByTestId("lead-call-outcome").select(outcome);
		cy.getByTestId("lead-call-follow-up").should("be.visible");
		cy.getByTestId("lead-call-suggestion").should("contain", "Contacted");
		cy.getByTestId("tab-overview").click();
		cy.getByTestId("lead-stage-select").select("Closed lost");
		cy.optionTexts("lead-lost-reason").should("include", reason);
	});

	it("an agent cannot open the call lists", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos/company/call-lists");
		cy.getByTestId("calllists-page").should("not.exist");
		cy.location("pathname").should("include", "no-access");
	});
});
