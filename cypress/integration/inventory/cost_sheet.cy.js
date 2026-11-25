// SOS-P7-07: a Company Admin sets the percentages, a dated price list and a payment plan (which must add up to
// 100); an Agent makes a cost sheet from a unit and opens it as a PDF; a Sales Manager only reads. The projects
// the spec makes (names start with "Gate Inventory ") and the percentages are removed afterwards.
context("SOS-P7-07: price lists, payment plans and cost sheets", () => {
	const rupees = (n) => `Rs ${new Intl.NumberFormat("en-IN").format(n)}`;
	const lineAmount = (key) =>
		cy
			.get(`[data-testid="sellos-cost-line-${key}"]`)
			.find('[data-testid="sellos-cost-amount"]');

	const openProject = (made) => {
		cy.intercept("POST", "**/sellos.inventory.pricing.project_pricing*").as("pricing");
		cy.visit(`/sellos/inventory/projects/${encodeURIComponent(made.project)}?tab=pricing`);
		cy.wait("@pricing");
	};
	const openUnitSheet = (made) => {
		cy.intercept("POST", "**/sellos.inventory.cost_sheet.cost_sheet_options*").as("options");
		cy.getByTestId("tab-units").click();
		cy.get(`[data-testid="sellos-unit-row"][data-number="1201"]`)
			.find('[data-testid="sellos-unit-cost-sheet"]')
			.click();
		cy.wait("@options");
		cy.location("pathname").should("contain", `/inventory/units/${made.unit}/cost-sheet`);
	};

	before(() => cy.bench("sellos.tests.ui_fixtures.remove_gate_pricing"));
	after(() => cy.bench("sellos.tests.ui_fixtures.remove_gate_pricing"));

	it("lets a Company Admin set the percentages, a price list and a plan, then makes a cost sheet", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_pricing", { prepared: 0 }).then((made) => {
			cy.signInFresh("company_admin");
			cy.expectApiStatus("sellos.inventory.pricing.save_payment_plan", 417);
			openProject(made);

			// Until the percentages and a price list exist, the cost sheet says what is missing.
			cy.getByTestId("rates").should("contain", "Not set yet");
			openUnitSheet(made);
			cy.getByTestId("cost-problem").should("contain", "no price list in force");
			cy.getByTestId("cost-make").should("not.exist");
			cy.go("back");
			cy.wait("@pricing");

			cy.intercept("POST", "**/sellos.inventory.pricing.save_cost_settings*").as(
				"saveRates"
			);
			cy.getByTestId("rate-stamp").type("6");
			cy.getByTestId("rate-registration").type("1");
			cy.getByTestId("rate-gst").type("5");
			cy.getByTestId("rates-save").click();
			cy.wait("@saveRates").its("response.statusCode").should("eq", 200);
			cy.getByTestId("pricing-notice").should("contain", "The percentages are saved.");

			cy.intercept("POST", "**/sellos.inventory.pricing.save_price_list*").as("saveList");
			cy.getByTestId("pricelist-open").click();
			cy.getByTestId("pricelist-title").type("Gate Inventory Spec List");
			cy.getByTestId("pricelist-from").type("2026-01-01");
			cy.getByTestId("pricelist-base").type("12000");
			cy.getByTestId("pricelist-rise").type("100");
			cy.getByTestId("pricelist-rise-floor").type("4");
			cy.getByTestId("pricelist-add-charge").click();
			cy.getByTestId("charge-kind-0").select("Preferred location");
			cy.getByTestId("charge-name-0").type("Garden");
			cy.getByTestId("charge-basis-0").select("Rate per sq ft");
			cy.getByTestId("charge-value-0").type("150");
			cy.getByTestId("pricelist-add-charge").click();
			cy.getByTestId("charge-kind-1").select("Parking");
			cy.getByTestId("charge-name-1").type("Parking");
			cy.getByTestId("charge-value-1").type("400000");
			cy.getByTestId("pricelist-add-charge").click();
			cy.getByTestId("charge-name-2").type("Development");
			cy.getByTestId("charge-value-2").type("250000");
			cy.getByTestId("charge-always-2").check({ force: true });
			cy.getByTestId("pricelist-save").click();
			cy.wait("@saveList").its("response.statusCode").should("eq", 200);
			cy.get('[data-testid="sellos-pricelist-row"][data-title="Gate Inventory Spec List"]')
				.should("have.attr", "data-in-force", "1")
				.and("contain", "In force")
				.and("contain", "Garden");

			// A plan that does not add up to 100 is refused, and the screen shows the running total.
			cy.intercept("POST", "**/sellos.inventory.pricing.save_payment_plan*").as("savePlan");
			cy.getByTestId("plan-open").click();
			cy.getByTestId("plan-name").type("Gate Inventory Spec Plan");
			cy.getByTestId("instalment-label-0").type("On booking");
			cy.getByTestId("instalment-due-0").type("On booking");
			cy.getByTestId("instalment-percent-0").type("20");
			cy.getByTestId("plan-add-instalment").click();
			cy.getByTestId("instalment-label-1").type("On slab");
			cy.getByTestId("instalment-due-1").type("On the 5th floor slab");
			cy.getByTestId("instalment-percent-1").type("30");
			cy.getByTestId("plan-add-instalment").click();
			cy.getByTestId("instalment-label-2").type("On possession");
			cy.getByTestId("instalment-due-2").type("On possession");
			cy.getByTestId("instalment-percent-2").type("40");
			cy.getByTestId("plan-total").should("contain", "Total: 90 percent");
			cy.getByTestId("plan-save").click();
			cy.wait("@savePlan");
			cy.getByTestId("pricing-error").should("contain", "must add up to 100");
			cy.getByTestId("instalment-percent-2").clear();
			cy.getByTestId("instalment-percent-2").type("50");
			cy.getByTestId("plan-total").should("contain", "Total: 100 percent");
			cy.getByTestId("plan-save").click();
			cy.wait("@savePlan").its("response.statusCode").should("eq", 200);
			cy.get('[data-testid="sellos-plan-row"][data-name="Gate Inventory Spec Plan"]').should(
				"contain",
				"On slab 30%"
			);

			cy.bench("sellos.tests.ui_fixtures.gate_pricing_state", {
				project: made.project,
			}).then((state) => {
				expect(state.price_lists).to.deep.eq(["Gate Inventory Spec List"]);
				expect(state.plans["Gate Inventory Spec Plan"]).to.deep.eq([20, 30, 50]);
				expect(state.rates).to.deep.eq([6, 1, 5]);
			});

			// The unit's cost sheet now works, with Garden chosen.
			openUnitSheet(made);
			cy.intercept("POST", "**/sellos.inventory.cost_sheet.make_cost_sheet*").as("make");
			cy.getByTestId("cost-plan").select("Gate Inventory Spec Plan");
			cy.getByTestId("cost-charge-Garden").check({ force: true });
			cy.getByTestId("cost-make").click();
			cy.wait("@make").its("response.statusCode").should("eq", 200);
			lineAmount("total").should("have.text", rupees(10155600));
			cy.getByTestId("cost-sheet-row").should("have.length", 1);
		});
	});

	it("lets an Agent make a cost sheet from a unit, see the schedule and open the PDF", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_pricing", { prepared: 1 }).then((made) => {
			cy.signInFresh("agent");
			openProject(made);
			cy.get('[data-testid="sellos-pricelist-row"]').should(
				"have.attr",
				"data-in-force",
				"1"
			);
			cy.getByTestId("pricelist-form").should("not.exist");
			cy.getByTestId("plan-form").should("not.exist");
			cy.getByTestId("rates-save").should("not.exist");
			cy.getByTestId("rates-text").should(
				"contain",
				"Stamp duty 6%, registration 1%, GST 5%"
			);
			openUnitSheet(made);
			cy.getByTestId("cost-list").should("contain", "Gate Inventory List");

			cy.intercept("POST", "**/sellos.inventory.cost_sheet.make_cost_sheet*").as("make");
			cy.getByTestId("cost-plan").select(`Gate Inventory Construction Plan ${made.tag}`);
			cy.getByTestId("cost-charge-Garden").check({ force: true });
			cy.getByTestId("cost-make").click();
			cy.wait("@make").its("response.statusCode").should("eq", 200);

			lineAmount("base").should("have.text", rupees(7800000));
			lineAmount("rise").should("have.text", rupees(520000));
			lineAmount("charge-Garden").should("have.text", rupees(97500));
			lineAmount("charge-Parking").should("have.text", rupees(400000));
			lineAmount("charge-Development").should("have.text", rupees(250000));
			lineAmount("agreement").should("have.text", rupees(9067500));
			lineAmount("stamp").should("have.text", rupees(544050));
			lineAmount("registration").should("have.text", rupees(90675));
			lineAmount("gst").should("have.text", rupees(453375));
			lineAmount("total").should("have.text", rupees(10155600));
			cy.getByTestId("cost-instalment-amount").then(($amounts) => {
				expect([...$amounts].map((el) => el.innerText)).to.deep.eq([
					rupees(2031120),
					rupees(3046680),
					rupees(5077800),
				]);
			});

			// The PDF opens as a PDF.
			cy.getByTestId("cost-pdf")
				.should("have.attr", "href")
				.then((href) => {
					cy.request({ url: href, encoding: "binary" }).then((response) => {
						expect(response.status).to.eq(200);
						expect(response.headers["content-type"]).to.contain("application/pdf");
						expect(response.body.slice(0, 4)).to.eq("%PDF");
					});
				});

			cy.bench("sellos.tests.ui_fixtures.gate_pricing_state", {
				project: made.project,
			}).then((state) => {
				expect(state.sheets).to.have.length(1);
				expect(state.sheets[0].total).to.eq(10155600);
				expect(state.sheets[0].stamp_duty_percent).to.eq(6);
			});
		});
	});

	it("lets a Sales Manager read the price lists but not change them or make a cost sheet", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_pricing", { prepared: 1 }).then((made) => {
			cy.signInFresh("sales_manager");
			openProject(made);
			cy.get('[data-testid="sellos-pricelist-row"]').should(
				"have.attr",
				"data-in-force",
				"1"
			);
			cy.getByTestId("plan-row").should("have.length", 1);
			cy.getByTestId("pricelist-form").should("not.exist");
			cy.getByTestId("plan-form").should("not.exist");
			cy.getByTestId("rates-save").should("not.exist");
			cy.getByTestId("unit-cost-sheet").should("not.exist");
		});
	});
});
