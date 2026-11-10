// SOS-P1-08: the consent warning on the lead screen for each status, against the real server.
// Consented shows no warning, Unknown and Registered DND show amber, Opted out shows red. The seeded
// leads come from sellos.crm.api, so the status is the one the production code computed.
context("SOS-P1-08: consent warning on the lead screen", () => {
	let leads;

	before(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_consent_leads").then((made) => {
			leads = made;
		});
	});

	// The seeded leads are committed, so a rollback never removes them (SOS-SETUP-24).
	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});

	const open = (status) => {
		cy.signInFresh("agent");
		cy.visit(`/sellos/crm/leads/${leads[status]}`);
		cy.getByTestId("lead-consent").should("have.attr", "data-status", status);
		cy.getByTestId("lead-consent-status").should("contain", status);
	};

	it("shows no warning for Consented", () => {
		open("Consented");
		cy.getByTestId("lead-consent-warning").should("not.exist");
		cy.getByTestId("lead-consent-record").should("contain", "Consent");
	});

	it("shows an amber warning for Unknown", () => {
		open("Unknown");
		cy.getByTestId("lead-consent-warning")
			.should("have.attr", "data-level", "amber")
			.and("contain", "Consent unknown");
	});

	it("shows an amber warning for Registered DND", () => {
		open("Registered DND");
		cy.getByTestId("lead-consent-warning")
			.should("have.attr", "data-level", "amber")
			.and("contain", "do not call");
	});

	it("shows a red warning for Opted out, with its source, and still lets the agent log a call", () => {
		open("Opted out");
		cy.getByTestId("lead-consent-warning")
			.should("have.attr", "data-level", "red")
			.and("contain", "WhatsApp");
		cy.getByTestId("lead-activity-type").select("Call");
		cy.getByTestId("lead-activity-notes").type("Called after the stop request");
		cy.getByTestId("lead-activity-form").submit();
		cy.getByTestId("lead-timeline-item").should("contain", "Called after the stop request");
	});

	it("refuses a consent record without an evidence link and accepts one with a link", () => {
		open("Unknown");
		cy.getByTestId("lead-consent-evidence").type("   ");
		cy.getByTestId("lead-consent-form").submit();
		cy.expectApiStatus("sellos.crm.api.record_consent", 417);
		cy.getByTestId("lead-consent-error").should("be.visible");
		cy.getByTestId("lead-consent").should("have.attr", "data-status", "Unknown");
		cy.getByTestId("lead-consent-evidence")
			.clear()
			.type("https://example.com/evidence/call-1");
		cy.getByTestId("lead-consent-form").submit();
		cy.getByTestId("lead-consent").should("have.attr", "data-status", "Consented");
		cy.getByTestId("lead-consent-warning").should("not.exist");
	});
});
