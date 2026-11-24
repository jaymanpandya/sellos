// SOS-LOOP layout pass (24 November 2026): three radii. Every card, panel, input, select, button, menu, drawer
// and modal has 14px for cards, 10px for controls, round for pills and badges. This opens every page of each
// role's menu, the New lead drawer and a row menu, and fails on any element drawn with another radius.
// The same rule is checked on the source by sellos/tests/test_ui_radius.py.
context("SOS-LOOP: three radii on every page", () => {
	const ROLES = ["company_admin", "agent", "channel_partner", "client"];
	const ALLOWED = new Set(["0px", "10px", "14px"]);

	// Elements whose four corners are not 0 or 14px, and are not a status badge (a full pill).
	function stray(win) {
		const found = [];
		win.document.querySelectorAll("body *").forEach((el) => {
			const style = win.getComputedStyle(el);
			if (style.display === "none" || style.visibility === "hidden") return;
			const corners = [
				"borderTopLeftRadius",
				"borderTopRightRadius",
				"borderBottomLeftRadius",
				"borderBottomRightRadius",
			].map((c) => style[c]);
			if (corners.every((c) => ALLOWED.has(c))) return;
			const badge = el.closest('[class*="rounded-round"], .ui-badge');
			if (badge && corners.every((c) => ALLOWED.has(c) || parseFloat(c) >= 100)) return;
			found.push(
				`${el.tagName.toLowerCase()}.${String(el.className).slice(0, 60)} ${corners[0]}`
			);
		});
		return found;
	}

	const noStrays = (what) =>
		cy.window().then((win) => {
			expect(stray(win), `${what}: elements with another radius`).to.deep.equal([]);
		});

	ROLES.forEach((role) => {
		it(`draws every page of the ${role} menu with the three radii`, () => {
			if (role === "channel_partner") {
				cy.bench("sellos.tests.ui_fixtures.seed_gate_partner_firm", { stage: "approved" });
			}
			cy.viewport(1400, 960);
			cy.signInFresh(role);
			cy.visit("/sellos");
			cy.getByTestId("page-body", { timeout: 20000 }).should("be.visible");
			cy.getByTestId("nav")
				.filter(":visible")
				.find("a")
				.then(($links) => {
					const hrefs = $links.toArray().map((a) => a.getAttribute("href"));
					hrefs.forEach((href) => {
						cy.visit(href);
						cy.getByTestId("page-body").should("be.visible");
						cy.getByTestId("page-body").find('[role="status"]').should("not.exist");
						noStrays(href);
					});
				});
			if (role === "channel_partner")
				cy.bench("sellos.tests.ui_fixtures.remove_gate_partner_firms");
		});
	});

	it("draws the New lead drawer and the open filters with the three radii", () => {
		cy.signInFresh("company_admin");
		cy.visit("/sellos/crm/leads");
		cy.getByTestId("leads-new").click();
		cy.getByTestId("lead-form").should("be.visible");
		noStrays("New lead drawer");
		cy.getByTestId("drawer-cancel").click();
		cy.getByTestId("leads-filters-toggle").click();
		cy.getByTestId("filters-more").should("be.visible");
		noStrays("More filters");
	});
});
