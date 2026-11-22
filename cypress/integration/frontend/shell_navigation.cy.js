// SOS-P0-10: the app shell in the browser, for every role. Replaces shell.test.js and
// AppShell.test.js. The company name, logo and colour are changed in the boot data the page is
// given, because that is where the app reads them.
import { PERSONAS, navFor } from "../../../frontend/src/personas";

const ROLE_KEYS = [
	"platform_admin",
	"company_admin",
	"sales_manager",
	"agent",
	"channel_partner",
	"client",
];

context("SOS-P0-10: app shell", () => {
	ROLE_KEYS.forEach((key) => {
		const persona = PERSONAS.find((p) => p.key === key);

		it(`${persona.role} sees only navigation inside its own areas`, () => {
			// Leave the previous role's page first: its late polling answers would set the old session
			// cookie again after this sign in, and the Today calls of this role would answer 400.
			cy.clearAllCookies();
			cy.visit("/login");
			cy.signInFresh(key);
			cy.bootOverride((boot) => {
				boot.company.name = "Pandya Realtors";
			});
			cy.visit("/sellos");
			if (key === "agent" || key === "sales_manager") {
				cy.getByTestId("today-counts", { timeout: 15000 }).should("be.visible");
			}
			const labels = navFor(persona).map((item) => item.label);
			expect(labels.length, "the persona has navigation").to.be.greaterThan(0);
			cy.getByTestId("nav")
				.find("a")
				.should("have.length", labels.length)
				.then(($links) => {
					expect([...$links].map((a) => a.innerText.trim())).to.deep.equal(labels);
				});
			cy.getByTestId("nav-home").should("contain", "Home");
			cy.getByTestId("brand-name").filter(":visible").should("contain", "Pandya Realtors");
			cy.getByTestId("signout").should("contain", "Sign out");
		});
	});

	it("a user with no SellOS role gets no navigation, the product name and the page content", () => {
		cy.signInFresh("basic");
		cy.bootOverride((boot) => {
			boot.company.name = "";
		});
		cy.visit("/sellos");
		cy.getByTestId("brand-name").filter(":visible").should("contain", "SellOS");
		cy.getByTestId("nav").find("a").should("have.length", 0);
		cy.getByTestId("page-body").find('[data-testid="sellos-no-access"]').should("exist");
	});

	it("shows the company name and the Home, Leads, Call queue, WhatsApp, Site visits, Inventory and Reports links for an agent", () => {
		cy.signInFresh("agent");
		cy.bootOverride((boot) => {
			boot.company.name = "Pandya Realtors";
		});
		cy.visit("/sellos");
		// Agents land on Today: let its lists finish loading, so leaving the page cuts no request off.
		cy.getByTestId("today-counts", { timeout: 15000 }).should("be.visible");
		cy.getByTestId("brand-name").filter(":visible").should("contain", "Pandya Realtors");
		cy.getByTestId("nav")
			.find("a")
			.then(($links) => {
				expect([...$links].map((a) => a.innerText.trim()).sort()).to.deep.equal([
					"Call queue",
					"Home",
					"Inventory", // SOS-P4-01
					"Leads",
					"Mandates", // SOS-P4-05
					"Reports", // SOS-P5-01
					"Sellers", // SOS-P4-04
					"Site visits",
					"WhatsApp", // SOS-P6-11
				]);
			});
	});

	it("shows the company logo when settings have one", () => {
		cy.signInFresh("agent");
		cy.bootOverride((boot) => {
			boot.company.logo = "/files/logo.png";
		});
		cy.visit("/sellos");
		// Agents land on Today: let its lists finish loading, so leaving the page cuts no request off.
		cy.getByTestId("today-counts", { timeout: 15000 }).should("be.visible");
		cy.getByTestId("brand-logo").first().should("have.attr", "src", "/files/logo.png");
	});

	it("applies the company colour to the page", () => {
		cy.signInFresh("agent");
		cy.bootOverride((boot) => {
			boot.company.brand_color = "#112233";
		});
		cy.visit("/sellos");
		// Agents land on Today: let its lists finish loading, so leaving the page cuts no request off.
		cy.getByTestId("today-counts", { timeout: 15000 }).should("be.visible");
		cy.document().then((doc) => {
			expect(doc.documentElement.style.getPropertyValue("--sos-brand")).to.eq("#112233");
		});
	});

	it("sign out posts to logout, clears the session and goes to login", () => {
		cy.signInFresh("agent");
		cy.intercept("POST", "**/api/method/logout").as("logout");
		cy.intercept("POST", "**/api/method/sellos.crm.api.today_screen").as("today");
		cy.visit("/sellos");
		// Agents land on Today: let its lists finish loading, so leaving the page cuts no request off.
		cy.getByTestId("today-counts", { timeout: 15000 }).should("be.visible");
		cy.wait("@today");
		cy.getByTestId("signout").click();
		cy.wait("@logout").its("request.method").should("eq", "POST");
		cy.location("pathname").should("eq", "/login");
	});

	it("sends the user to sign in again when the session has expired", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos");
		// Agents land on Today: let its lists finish loading, so leaving the page cuts no request off.
		cy.getByTestId("today-counts", { timeout: 15000 }).should("be.visible");
		cy.getByTestId("app-shell").should("exist");
		cy.intercept("GET", "**/api/method/frappe.auth.get_logged_user*", {
			statusCode: 200,
			body: { message: "Guest" },
		}).as("whoami");
		cy.document().then((doc) => doc.dispatchEvent(new Event("visibilitychange")));
		cy.wait("@whoami");
		cy.location("pathname").should("eq", "/login");
	});

	it("does not send a signed in user to login when the session is still good", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos");
		// Agents land on Today: let its lists finish loading, so leaving the page cuts no request off.
		cy.getByTestId("today-counts", { timeout: 15000 }).should("be.visible");
		cy.getByTestId("app-shell").should("exist");
		cy.intercept("GET", "**/api/method/frappe.auth.get_logged_user*", {
			statusCode: 200,
			body: { message: "sos_test_agent@example.com" },
		}).as("whoami");
		cy.document().then((doc) => doc.dispatchEvent(new Event("visibilitychange")));
		cy.wait("@whoami");
		cy.location("pathname").should("eq", "/sellos");
	});
});
