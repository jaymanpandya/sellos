// Visual walk through (docs/UI_STANDARD.md): opens every page in each role's menu and saves a screenshot.
// The page list is read from the live sidebar, so a page added to personas.js is walked with no edit here.
// Screenshots land in cypress/screenshots/visual/walkthrough.cy.js/<role>/ as <nn>-<page>.png (desktop) and
// phone-<nn>-<page>.png (375x812, Home and Leads). Run:
//   bench --site sellos_test.localhost run-ui-tests sellos --headless --spec cypress/integration/visual/walkthrough.cy.js
// The global checks in cypress/support/e2e.js also fail the walk on any API 4xx/5xx or console error.

const ROLES = [
	{ role: "company_admin", label: "company-admin" },
	{ role: "agent", label: "agent" },
	{ role: "channel_partner", label: "partner" },
	{ role: "client", label: "client" },
];

const slug = (text) =>
	text
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-|-$/g, "");

// The page is drawn: the body is visible, no loading skeleton is left in it, and it is not the no access page.
function pageDrawn() {
	cy.getByTestId("page-body", { timeout: 20000 }).should("be.visible");
	cy.getByTestId("page-body").find('[role="status"]').should("not.exist");
	cy.getByTestId("no-access").should("not.exist");
}

// The menu links of the signed in role: [{ href, label, icons }], read from the sidebar that is on screen.
function menuLinks() {
	return cy
		.getByTestId("nav")
		.filter(":visible")
		.find("a")
		.then(($links) =>
			$links.toArray().map((a) => ({
				href: a.getAttribute("href"),
				label: a.textContent.trim(),
				icons: a.querySelectorAll('[class*="lucide-"]').length,
			}))
		);
}

ROLES.forEach(({ role, label }) => {
	describe(`Visual walk through: ${label}`, () => {
		before(() => {
			cy.bench("sellos.tests.ui_fixtures.seed_agent_leads");
		});
		after(() => {
			cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
		});

		it("opens every page in the menu and saves a screenshot of each", () => {
			cy.viewport(1400, 960);
			cy.signInFresh(role);
			cy.visit("/sellos");
			pageDrawn();
			menuLinks().then((links) => {
				expect(links.length, "menu items").to.be.greaterThan(0);
				links.forEach((link) => {
					expect(link.icons, `${link.label} has an icon`).to.eq(1);
				});
				links.forEach((link, index) => {
					const n = String(index + 1).padStart(2, "0");
					cy.visit(link.href);
					pageDrawn();
					cy.screenshot(`${label}/${n}-${slug(link.label)}`, {
						capture: "viewport",
						overwrite: true,
					});
				});
			});
		});

		it("saves a phone screenshot of Home and of Leads", () => {
			cy.viewport(375, 812);
			cy.signInFresh(role);
			cy.visit("/sellos");
			pageDrawn();
			cy.screenshot(`${label}/phone-01-home`, { capture: "viewport", overwrite: true });
			cy.getByTestId("phone-nav").should("be.visible");
			cy.viewport(1400, 960);
			menuLinks().then((links) => {
				const leads = links.find((link) => link.label === "Leads");
				if (!leads) return;
				cy.viewport(375, 812);
				cy.visit(leads.href);
				pageDrawn();
				cy.screenshot(`${label}/phone-02-leads`, { capture: "viewport", overwrite: true });
			});
		});
	});
});
