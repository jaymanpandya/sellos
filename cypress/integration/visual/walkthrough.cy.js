// Visual walk through (docs/UI_STANDARD.md): opens every page in each role's menu and saves a screenshot.
// The page list is read from the live sidebar, so a page added to personas.js is walked with no edit here.
// Screenshots land in cypress/screenshots/visual/walkthrough.cy.js/<role>/ as <nn>-<page>.png (desktop) and
// phone-<nn>-<page>.png (390x844, every page). Run:
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

// A phone page must not scroll sideways: its content is no wider than the page (a card that sticks out by a few
// pixels is invisible in a screenshot and fails a customer's thumb).
function noSidewaysScroll(what) {
	cy.document().then((doc) => {
		const root = doc.documentElement;
		expect(root.scrollWidth, `${what}: page width`).to.be.at.most(root.clientWidth);
	});
}

// Lists (docs/DESIGN_SYSTEM.md, "Lists", rules a to f), read from the tables that are drawn. At 1440 a table does
// not clip or scroll sideways; no cell holds a button, a field or a link styled as a button but the row menu; no
// text wraps beyond two lines; no name ends in a source word; no cell is a bare dash. At 390 a table is cards.
const SOURCE_WORDS =
	/\b(Referral|Walk in|Walk-in|Website|Portal|Facebook|Instagram|Google|99acres|MagicBricks|Housing)\s*$/i;
// Every problem of every page is collected and reported together at the end of the walk, so one run shows them all.
const problems = [];
function listRules(what, width) {
	cy.get("body").then(($body) => {
		const tables = $body.find('[data-testid="sellos-table-view"] table');
		const cards = $body.find('[data-testid="sellos-card-view"]');
		const problem = (text) => problems.push(`${what}: ${text}`);
		if (width >= 1024 && cards.length) problem(`a card view at ${width}`);
		if (width < 1024 && tables.length) problem(`a table at ${width}`);
		tables.each((_, table) => {
			const box = table.closest(".ui-table-scroll");
			if (box.scrollWidth > box.clientWidth + 1)
				problem(`the table scrolls sideways (${box.scrollWidth} > ${box.clientWidth})`);
			Array.from(table.querySelectorAll("tbody td")).forEach((td) => {
				const label = `"${td.innerText.trim().slice(0, 40)}"`;
				const bad = td.querySelectorAll(
					'button:not([data-testid="sellos-row-menu-button"]):not([role="checkbox"]), select, textarea, input:not([type="checkbox"]), a.ui-button, [class*="ui-button"]'
				);
				if (bad.length) problem(`${label} holds a control in a row`);
				if (/^[-\u2013\u2014]$/.test(td.innerText.trim()))
					problem(`${label} is a bare dash`);
				if (td.scrollWidth > td.clientWidth + 1) problem(`${label} is clipped`);
				td.querySelectorAll("*").forEach((el) => {
					const own = Array.from(el.childNodes).some(
						(n) => n.nodeType === 3 && n.textContent.trim()
					);
					if (!own) return;
					const style = getComputedStyle(el);
					if (style.display === "inline") return;
					const line = parseFloat(style.lineHeight) || parseFloat(style.fontSize) * 1.4;
					if (el.getBoundingClientRect().height / line > 2.1)
						problem(`${label} wraps beyond two lines`);
				});
			});
			table.querySelectorAll('[data-testid="sellos-name-cell-name"]').forEach((el) => {
				if (SOURCE_WORDS.test(el.textContent.trim()))
					problem(`the name "${el.textContent.trim()}" carries a source`);
			});
		});
	});
}
const noListProblems = () =>
	cy.then(() => {
		const found = problems.splice(0);
		expect(found.join("\n"), "list rule problems").to.eq("");
	});

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
			// A partner with no firm is refused by the server (403), as it should be; the walk through
			// shows a partner who has an approved firm.
			if (role === "channel_partner") {
				cy.bench("sellos.tests.ui_fixtures.seed_gate_partner_firm", { stage: "approved" });
			}
		});
		after(() => {
			cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
			if (role === "channel_partner") {
				cy.bench("sellos.tests.ui_fixtures.remove_gate_partner_firms");
			}
		});

		it("opens every page in the menu and saves a screenshot of each", () => {
			cy.viewport(1440, 960);
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
					// At 1440 nothing is cut off or scrolls sideways either (docs/DESIGN_SYSTEM.md, rule 7).
					noSidewaysScroll(`${link.label} at 1440`);
					listRules(`${link.label} at 1440`, 1440);
					cy.screenshot(`${label}/${n}-${slug(link.label)}`, {
						capture: "viewport",
						overwrite: true,
					});
				});
				noListProblems();
			});
		});

		it("opens every page at 390 wide, nothing scrolls sideways, and saves a screenshot of each", () => {
			cy.viewport(1440, 960);
			cy.signInFresh(role);
			cy.visit("/sellos");
			pageDrawn();
			menuLinks().then((links) => {
				cy.viewport(390, 844);
				links.forEach((link, index) => {
					const n = String(index + 1).padStart(2, "0");
					cy.visit(link.href);
					pageDrawn();
					noSidewaysScroll(`${link.label} at 390`);
					listRules(`${link.label} at 390`, 390);
					if (index === 0) cy.getByTestId("phone-nav").should("be.visible");
					cy.screenshot(`${label}/phone-${n}-${slug(link.label)}`, {
						capture: "viewport",
						overwrite: true,
					});
				});
				noListProblems();
			});
		});
	});
});
