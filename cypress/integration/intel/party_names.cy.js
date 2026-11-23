// SOS-P3-12: Index II buyer and seller names are visible only to a Company Admin, are never searchable and
// every view is logged. Goes through the real server, signed in as each role.
context("SOS-P3-12: party names", () => {
	let seeded;
	const method = "sellos.intel.party_names.get_party_names";
	// The method is POST only, so its access log row is committed.
	const viewNames = (record) =>
		cy.request({
			url: `/api/method/${method}`,
			method: "POST",
			body: { source_record_id: record },
			failOnStatusCode: false,
		});

	before(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_party_names").then((s) => {
			seeded = s;
		});
	});
	after(() => cy.bench("sellos.tests.ui_fixtures.remove_party_names"));

	it("a Company Admin sees the names and the view is logged", () => {
		cy.signInFresh("company_admin");
		viewNames(seeded.record).then((res) => {
			expect(res.status).to.eq(200);
			expect(JSON.stringify(res.body.message)).to.contain(seeded.buyer);
			expect(JSON.stringify(res.body.message)).to.contain(seeded.seller);
		});
		cy.apiAs("frappe.client.get_count", {
			doctype: "Party Name Access Log",
			filters: JSON.stringify({ source_record_id: seeded.record }),
		}).then((res) => {
			expect(res.body.message).to.eq(1);
		});
	});

	["agent", "sales_manager", "channel_partner", "client", "platform_admin"].forEach((role) => {
		it(`${role} gets no name from the method or the generic paths`, () => {
			cy.signInFresh(role);
			viewNames(seeded.record).then((res) => {
				expect(res.status).to.eq(403);
				expect(JSON.stringify(res.body), "method answer").to.not.contain(seeded.buyer);
			});
			cy.genericReads("Party Name", "none").then((results) => {
				results.forEach(({ path, text }) => {
					expect(text, `${path} as ${role}`).to.not.contain(seeded.buyer);
					expect(text, `${path} as ${role}`).to.not.contain(seeded.seller);
				});
			});
		});
	});

	it("a name cannot be searched, even by a Company Admin", () => {
		cy.signInFresh("company_admin");
		const filters = JSON.stringify({ party_name: ["like", `%${seeded.buyer.slice(0, 12)}%`] });
		cy.apiAs("frappe.client.get_list", {
			doctype: "Party Name",
			fields: '["party_name"]',
			filters,
		}).then((res) => {
			expect(JSON.stringify(res.body)).to.not.contain(seeded.buyer);
		});
		viewNames(seeded.buyer).then((res) => {
			expect(res.status).to.eq(200);
			expect(res.body.message).to.deep.eq([]);
		});
	});
});
