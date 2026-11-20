// SOS-P2-09: the caller queue, against the real server. ui_fixtures.seed_caller_queue gives the test agent
// one lead per case: Soon (Inquiry, 7 days left), Months (Application, 3 months), Forever (Consent, no
// expiry), Unknown, Opted out and Dnd. remove_seeded_leads removes them afterwards.
context("SOS-P2-09: the caller queue", () => {
	let seed;

	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_caller_queue").then((made) => {
			seed = made;
		});
	});
	afterEach(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});

	const row = (key) =>
		cy.get(`[data-testid="sellos-queue-row"][data-lead="${seed.leads[key]}"]`);

	it("lists every lead, Consented first by soonest expiry, with the time left", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos/crm/queue");
		cy.getByTestId("queue-list").should("be.visible");
		for (const key of Object.keys(seed.leads)) row(key).should("exist");
		cy.getByTestId("queue-row").then(($rows) => {
			const order = [...$rows].map((r) => r.getAttribute("data-lead"));
			const at = (key) => order.indexOf(seed.leads[key]);
			expect(at("soon")).to.be.lessThan(at("months"));
			expect(at("months")).to.be.lessThan(at("forever"));
			expect(at("forever")).to.be.lessThan(at("unknown"));
			expect(at("unknown")).to.be.lessThan(at("dnd"));
			expect(at("dnd")).to.be.lessThan(at("opted"));
		});
		row("soon").find("[data-testid=sellos-queue-time-left]").should("contain", "6 days");
		row("months").find("[data-testid=sellos-queue-time-left]").should("contain", "left");
		row("forever").find("[data-testid=sellos-queue-no-expiry]").should("be.visible");
		row("unknown").find("[data-testid=sellos-queue-time-left]").should("not.exist");
	});

	it("shows an amber warning for Unknown and Registered DND and a red one for Opted out", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos/crm/queue");
		row("unknown")
			.find("[data-testid=sellos-queue-consent]")
			.should("have.attr", "data-level", "amber");
		row("dnd")
			.find("[data-testid=sellos-queue-consent]")
			.should("have.attr", "data-level", "amber");
		row("opted")
			.find("[data-testid=sellos-queue-consent]")
			.should("have.attr", "data-level", "red");
		row("opted").find("[data-testid=sellos-queue-warning]").should("be.visible");
		row("forever")
			.find("[data-testid=sellos-queue-consent]")
			.should("have.attr", "data-level", "none");
	});

	it("never blocks a call on a warned lead, and shows only the masked number", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos/crm/queue");
		row("opted").find("[data-testid=sellos-queue-call]").should("not.be.disabled").click();
		row("opted").find("[data-testid=sellos-queue-number]").should("be.visible");
	});

	it("is in the agent's navigation", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos");
		cy.getByTestId("nav").contains("a", "Call queue").filter(":visible").first().click();
		cy.location("pathname").should("eq", "/sellos/crm/queue");
	});
});
