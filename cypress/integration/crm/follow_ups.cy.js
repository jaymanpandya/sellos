// SOS-P1-22: follow ups and reminders, against the real server. The leads come from sellos.crm.api
// through seed_board_leads: the test agent owns Gate Board Agent A (Qualified, made now) and Gate Board Old
// (New, made 30 days ago, so it has had no follow up for longer than the untouched days). Every follow up
// is made through the screen, and the seeded leads, with their follow ups, are removed afterwards.
context("SOS-P1-22: completing a follow up", () => {
	let seed;

	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_board_leads").then((made) => {
			seed = made;
		});
	});
	afterEach(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
		cy.bench("sellos.tests.ui_fixtures.reset_follow_up_settings");
	});

	const openLead = (key = "agent_a") => {
		cy.signInFresh("agent");
		cy.visit(`/sellos/crm/leads/${seed.leads[key]}`);
		cy.getByTestId("lead-next-follow-up").should("be.visible");
	};

	// Add a follow up and wait until it is saved and the lead has been read again.
	const addFollowUp = (title, when) => {
		cy.intercept("POST", "**/api/method/sellos.crm.api.save_task*").as("saveTask");
		cy.getByTestId("lead-task-title").type(title);
		cy.getByTestId("lead-task-due").type(when);
		cy.getByTestId("lead-task-save").click();
		cy.wait("@saveTask").its("response.statusCode").should("eq", 200);
		cy.getByTestId("lead-next-follow-up").should("contain", title);
	};

	const finish = () => {
		cy.intercept("POST", "**/api/method/sellos.crm.api.complete_follow_up*").as("complete");
		cy.getByTestId("lead-done-save").click();
	};

	it("shows the next follow up on the lead, and none when there is none", () => {
		openLead();
		cy.getByTestId("lead-next-follow-up").should("contain", "No open follow up");
		addFollowUp("Send the brochure", "2030-03-04T10:30");
		cy.getByTestId("lead-next-follow-up").should("contain", "4 Mar 2030, 10:30");
		cy.getByTestId("lead-follow-up-overdue").should("not.exist");
	});

	it("asks for the call outcome or a note before it marks a follow up done", () => {
		openLead();
		addFollowUp("Call about the price", "2030-03-04T10:30");
		cy.getByTestId("lead-task-done").click();
		cy.getByTestId("lead-done-form").should("be.visible");
		// With neither an outcome nor a note, it stays open and says what is needed.
		finish();
		cy.getByTestId("lead-done-error").should(
			"contain",
			"Choose the call outcome or write a note."
		);
		cy.getByTestId("lead-next-follow-up").should("contain", "Call about the price");
		// A note is enough.
		cy.getByTestId("lead-done-notes").type("Buyer will decide on Sunday");
		finish();
		cy.wait("@complete").its("response.statusCode").should("eq", 200);
		cy.getByTestId("lead-next-follow-up").should("contain", "No open follow up");
		cy.getByTestId("lead-done-form").should("not.exist");
		cy.getByTestId("lead-timeline-item")
			.contains("Buyer will decide on Sunday")
			.closest("[data-testid=sellos-lead-timeline-item]")
			.should("contain", "Note");
		cy.getByTestId("lead-timeline-item")
			.contains("Call about the price")
			.closest("[data-testid=sellos-lead-timeline-item]")
			.should("contain", "Done");
	});

	it("completes it with a call outcome, and an outcome that needs one sets the next follow up", () => {
		openLead();
		addFollowUp("First call", "2030-03-04T10:30");
		cy.getByTestId("lead-task-done").click();
		cy.getByTestId("lead-done-outcome").select("Call back later");
		cy.getByTestId("lead-done-follow-up").should("be.visible").and("have.attr", "required");
		cy.getByTestId("lead-done-follow-up").type("2030-03-09T16:00");
		finish();
		cy.wait("@complete").its("response.statusCode").should("eq", 200);
		cy.getByTestId("lead-next-follow-up")
			.should("contain", "Follow up: Call back later")
			.and("contain", "9 Mar 2030, 16:00");
		cy.getByTestId("lead-timeline-outcome").should("contain", "Call back later");
	});

	it("flags an overdue follow up on the lead and lists overdue ones in the leads list", () => {
		openLead();
		addFollowUp("Missed call", "2020-01-01T10:00");
		cy.getByTestId("lead-follow-up-overdue").should("be.visible");
		cy.intercept("POST", "**/sellos.crm.api.list_leads*").as("list");
		cy.visit("/sellos/crm/leads?follow_up=overdue");
		cy.wait("@list").its("response.statusCode").should("eq", 200);
		cy.getByTestId("lead-row").should("have.length", 1);
		cy.getByTestId("lead-row")
			.should("contain", seed.agent_a)
			.and("contain", "Follow up overdue")
			.and("contain", "1 Jan");
	});

	it("flags an untouched lead and sorts the list by the next follow up", () => {
		openLead();
		addFollowUp("Later call", "2030-03-04T10:30");
		cy.intercept("POST", "**/sellos.crm.api.list_leads*").as("list");
		cy.visit("/sellos/crm/leads?follow_up=untouched");
		cy.wait("@list").its("response.statusCode").should("eq", 200);
		cy.getByTestId("lead-row").should("contain", seed.old).and("not.contain", seed.agent_a);
		cy.getByTestId("follow-up-untouched").should("contain", "3 days");
		cy.visit("/sellos/crm/leads?sort=next_follow_up");
		cy.wait("@list").its("response.statusCode").should("eq", 200);
		cy.getByTestId("lead-row").first().should("contain", seed.agent_a);
	});

	it("lets the Company Admin set the days for the untouched flag", () => {
		cy.signInFresh("company_admin");
		cy.visit("/sellos/company/call-lists");
		cy.getByTestId("calllists-untouched-days").should("have.value", "3");
		cy.intercept("POST", "**/api/method/sellos.crm.api.save_follow_up_settings*").as("save");
		cy.getByTestId("calllists-untouched-days").clear().type("40");
		cy.getByTestId("calllists-untouched-save").click();
		cy.wait("@save").its("response.statusCode").should("eq", 200);
		cy.getByTestId("calllists-untouched-saved").should("be.visible");
		// At 40 days the 30 day old lead is no longer untouched.
		cy.signInFresh("agent");
		cy.intercept("POST", "**/sellos.crm.api.list_leads*").as("list");
		cy.visit("/sellos/crm/leads?follow_up=untouched");
		cy.wait("@list").its("response.statusCode").should("eq", 200);
		cy.getByTestId("leads-empty").should("be.visible");
	});
});
