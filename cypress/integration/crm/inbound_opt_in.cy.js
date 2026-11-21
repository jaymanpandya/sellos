// SOS-P2-08: the enquiry page, against the real server. ui_fixtures.seed_enquiry_page sets the consent wording
// and gives the spec the form key of the link and a phone number from sellos.tests.phones. enquiry_outcome reads
// back the lead state, and remove_enquiry_page removes it all. The page needs no sign in.
context("SOS-P2-08: the enquiry page", () => {
	let seed;

	beforeEach(() => {
		cy.signOut();
		cy.bench("sellos.tests.ui_fixtures.seed_enquiry_page").then((made) => {
			seed = made;
		});
	});
	afterEach(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_enquiry_page");
	});

	const fill = () => {
		cy.getByTestId("enquiry-name").type("Gate Enquiry Visitor");
		cy.getByTestId("enquiry-phone").type(seed.phone);
	};
	const outcome = () => cy.bench("sellos.tests.ui_fixtures.enquiry_outcome");

	it("shows the consent wording and records an inquiry consent on the New stage", () => {
		cy.visit(`/enquiry?k=${seed.key}`);
		cy.getByTestId("enquiry-wording").should("contain", seed.wording);
		cy.intercept("POST", "/api/method/sellos.crm.enquiry.submit_enquiry").as("submit");
		fill();
		cy.getByTestId("enquiry-submit").click();
		cy.wait("@submit").its("response.statusCode").should("eq", 200);
		cy.getByTestId("enquiry-result")
			.should("have.attr", "data-state", "thanks")
			.and("contain", "Your reference is");
		outcome().then((state) => {
			expect(state.consent_status).to.eq("Consented");
			expect(state.records).to.deep.eq(["Inquiry"]);
			expect(state.stage).to.eq(state.first_stage);
			expect(state.source).to.eq("Website");
			expect(state.evidence_private).to.eq(true);
		});
	});

	it("records a stop request as Opted out", () => {
		cy.visit(`/enquiry?k=${seed.key}`);
		fill();
		cy.getByTestId("enquiry-stop").check();
		cy.getByTestId("enquiry-submit").click();
		cy.getByTestId("enquiry-result").should("have.attr", "data-state", "thanks");
		outcome().then((state) => {
			expect(state.consent_status).to.eq("Opted out");
			expect(state.records).to.deep.eq([]);
		});
	});

	it("refuses a wrong key with a short answer and writes nothing", () => {
		cy.expectApiStatus("sellos.crm.enquiry.submit_enquiry", 400);
		cy.visit("/enquiry?k=not-the-key");
		fill();
		cy.getByTestId("enquiry-submit").click();
		cy.getByTestId("enquiry-result")
			.should("have.attr", "data-state", "refused")
			.and("contain", "We could not take this form");
		outcome().then((state) => expect(state.lead).to.eq(null));
	});

	it("says the link is not complete when it has no key", () => {
		cy.visit("/enquiry");
		cy.getByTestId("enquiry-incomplete").should("be.visible");
		cy.getByTestId("enquiry-form").should("not.exist");
	});
});
