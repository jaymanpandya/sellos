// SOS-P7-10: an Agent books an Available unit from their lead: one step makes the deal, marks the unit
// Booked and moves the lead to Booking; cancelling needs a reason, frees the unit and leaves the stage. The
// project (names start with "Gate Inventory ") and the lead are removed afterwards.
context("SOS-P7-10: book a unit from the pipeline", () => {
	let made;

	before(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_inventory");
		cy.bench("sellos.tests.ui_fixtures.make_gate_booking").then((result) => {
			made = result;
		});
	});
	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_inventory");
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});

	it("books a unit from the lead and cancels the booking with a reason", () => {
		cy.signInFresh("agent");
		cy.expectApiStatus("sellos.inventory.bookings.book_unit", 417);
		cy.expectApiStatus("sellos.inventory.bookings.cancel_booking", 417);
		cy.intercept("POST", "**/sellos.inventory.bookings.booking_panel*").as("panel");
		cy.visit(`/sellos/crm/leads/${encodeURIComponent(made.lead)}`);
		cy.wait("@panel");
		cy.getByTestId("lead-booking").should("be.visible");

		// A booking needs its price: the form says so and nothing changes.
		cy.getByTestId("booking-unit").select(made.units.G101);
		cy.intercept("POST", "**/sellos.inventory.bookings.book_unit*").as("book");
		cy.getByTestId("booking-confirm").click();
		cy.wait("@book");
		cy.getByTestId("booking-error").should("be.visible");
		cy.bench("sellos.tests.ui_fixtures.gate_booking_state", { lead: made.lead }).then(
			(state) => {
				expect(state.deals).to.have.length(0);
			}
		);

		cy.getByTestId("booking-price").type("8000000");
		cy.getByTestId("booking-amount").type("100000");
		cy.getByTestId("booking-confirm").click();
		cy.wait("@book").its("response.statusCode").should("eq", 200);
		cy.getByTestId("booking-row").should("have.length", 1);
		cy.getByTestId("lead-stage").should("have.attr", "data-stage", "Booking");
		cy.bench("sellos.tests.ui_fixtures.gate_booking_state", { lead: made.lead }).then(
			(state) => {
				expect(state.stage).to.eq("Booking");
				expect(state.deals).to.have.length(1);
				expect(state.deals[0].unit).to.eq(made.units.G101);
				expect(state.deals[0].unit_status).to.eq("Booked");
				expect(state.deals[0].price).to.eq(8000000);
				expect(state.deals[0].booking_amount).to.eq(100000);
				expect(state.deals[0].deal_status).to.eq("Active");
			}
		);

		cy.getByTestId("booking-cancel-open").click();
		cy.intercept("POST", "**/sellos.inventory.bookings.cancel_booking*").as("cancel");
		cy.getByTestId("booking-cancel-confirm").click();
		cy.wait("@cancel");
		cy.getByTestId("booking-error").should("be.visible");
		cy.getByTestId("booking-cancel-reason").type("Gate buyer withdrew");
		cy.getByTestId("booking-cancel-confirm").click();
		cy.wait("@cancel").its("response.statusCode").should("eq", 200);
		cy.getByTestId("booking-cancelled").should("have.length", 1);
		cy.getByTestId("booking-row").should("not.exist");
		cy.getByTestId("lead-stage").should("have.attr", "data-stage", "Booking");
		cy.bench("sellos.tests.ui_fixtures.gate_booking_state", { lead: made.lead }).then(
			(state) => {
				expect(state.stage).to.eq("Booking");
				expect(state.deals[0].deal_status).to.eq("Cancelled");
				expect(state.deals[0].unit_status).to.eq("Available");
				expect(state.deals[0].cancellation_reason).to.eq("Gate buyer withdrew");
			}
		);
	});
});
