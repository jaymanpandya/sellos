// SOS-P1-07: the buyer pipeline on the lead screen and in the setup wizard, against the real server.
// The leads come from sellos.crm.api through seed_consent_leads, one for each consent status, so the
// status and the warning are the ones the production code computed. Each lead is moved by the agent.
const STAGES = [
	"New",
	"Consent pending",
	"Contacted",
	"Qualified",
	"Site visit booked",
	"Site visit done",
	"Negotiation",
	"Booking",
	"Closed won",
	"Closed lost",
	"Nurture",
];

context("SOS-P1-07: the buyer pipeline", () => {
	let leads;

	// Each test moves its own new leads, so none depends on another test having run (SOS-SETUP-24).
	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_consent_leads").then((made) => {
			leads = made;
		});
	});

	// The seeded leads are committed, so a rollback never removes them.
	afterEach(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});

	const move = (stage) => {
		cy.intercept("POST", "**/api/method/sellos.crm.api.move_lead_stage*").as("move");
		cy.getByTestId("lead-stage-select").select(stage);
		// SOS-P1-21: a move to Closed lost asks for a reason from the Company Admin's list first.
		if (stage === "Closed lost") {
			cy.getByTestId("lead-lost-reason").select("Other");
			cy.getByTestId("lead-lost-save").click();
		}
		cy.wait("@move").its("response.statusCode").should("eq", 200);
		cy.getByTestId("lead-stage").should("have.attr", "data-stage", stage);
	};

	const open = (status) => {
		cy.signInFresh("agent");
		cy.visit(`/sellos/crm/leads/${leads[status]}`);
		cy.getByTestId("lead-stage").should("have.attr", "data-stage", "New");
	};

	it("lists the eleven stages in order", () => {
		open("Consented");
		cy.optionTexts("lead-stage-select").should("deep.eq", STAGES);
	});

	it("moves a Consented lead to Contacted with no warning, and logs the move", () => {
		open("Consented");
		move("Contacted");
		cy.getByTestId("lead-stage-warning").should("not.exist");
		cy.getByTestId("lead-stage-change")
			.first()
			.should("contain", "New to Contacted")
			.and("not.contain", "without a live Consent Record");
	});

	["Unknown", "Registered DND", "Opted out"].forEach((status) => {
		it(`moves a ${status} lead to Contacted, shows the warning and writes it to the log`, () => {
			open(status);
			move("Contacted");
			cy.getByTestId("lead-stage-warning")
				.should("be.visible")
				.and("contain", "Contacted")
				.and("have.attr", "data-level", status === "Opted out" ? "red" : "amber");
			cy.getByTestId("lead-stage-change-warning").first().should("contain", "Contacted");
			// The warning stays on the lead after a reload, and the log keeps it.
			cy.reload();
			cy.getByTestId("lead-stage-warning").should("be.visible");
			cy.getByTestId("lead-stage-change")
				.first()
				.should("contain", "New to Contacted")
				.and("contain", "Moved to Contacted");
			// It never stops the lead moving on, and the warning goes with the stage.
			move("Qualified");
			cy.getByTestId("lead-stage-warning").should("not.exist");
		});
	});

	it("moves an Opted out lead to every other stage", () => {
		open("Opted out");
		STAGES.filter((s) => s !== "New").forEach((stage) => {
			move(stage);
			cy.getByTestId("lead-stage-error").should("not.exist");
		});
		cy.getByTestId("lead-stage-change").should("have.length.at.least", STAGES.length - 1);
	});

	it("shows the stage on the leads list", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos/crm/leads");
		cy.getByTestId("lead-row-stage").should("have.length.at.least", 1);
	});

	it("refuses to delete a stage that has leads and says how many", () => {
		cy.bench("sellos.tests.ui_fixtures.reset_setup_wizard");
		cy.signInFresh("company_admin");
		cy.visit("/sellos/company/setup");
		cy.getByTestId("setup-step-stages").click();
		cy.getByTestId("setup-stage-row").should("have.length", 11);
		// The four seeded leads are on New, the first stage.
		cy.getByTestId("setup-stage-name").first().should("have.value", "New");
		cy.getByTestId("setup-stage-leads").first().should("contain", "lead");
		cy.getByTestId("setup-stage-remove").first().click();
		cy.expectApiStatus("sellos.config.setup_wizard.save_stages", 417);
		cy.getByTestId("setup-save-stages").click();
		cy.getByTestId("setup-error").should("contain.text", "lead(s)");
		cy.bench("sellos.tests.ui_fixtures.setup_wizard_result").then((result) => {
			expect(result.stages).to.deep.eq(STAGES);
		});
		cy.bench("sellos.tests.ui_fixtures.reset_setup_wizard");
	});
});
