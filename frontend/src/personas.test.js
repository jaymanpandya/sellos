import { describe, expect, it } from "vitest";

import { PERSONAS, inAreas, navLabel, personaFor, routeArea } from "./personas";

describe("personas", () => {
	it("defines the five roles, highest priority first", () => {
		expect(PERSONAS.map((p) => p.role)).toEqual([
			"SellOS Platform Admin",
			"SellOS Company Admin",
			"SellOS Agent",
			"SellOS Channel Partner",
			"SellOS Client",
		]);
	});

	it("gives no persona to a user without a SellOS role", () => {
		expect(personaFor([])).toBeNull();
		expect(personaFor(undefined)).toBeNull();
		expect(personaFor(["System Manager", "Guest"])).toBeNull();
	});

	it("maps each SellOS role to its own persona", () => {
		for (const persona of PERSONAS) {
			expect(personaFor([persona.role]).key).toBe(persona.key);
		}
	});

	it("gives a user with several roles the highest priority persona", () => {
		expect(personaFor(["SellOS Agent", "SellOS Company Admin"]).key).toBe("company_admin");
		expect(personaFor(["SellOS Client", "SellOS Platform Admin"]).key).toBe("platform_admin");
	});

	it("keeps clients and partners out of the CRM area", () => {
		expect(inAreas(personaFor(["SellOS Agent"]), "crm")).toBe(true);
		expect(inAreas(personaFor(["SellOS Client"]), "crm")).toBe(false);
		expect(inAreas(personaFor(["SellOS Channel Partner"]), "crm")).toBe(false);
		expect(inAreas(null, "home")).toBe(false);
	});

	it("falls back to the home area when a route has none", () => {
		expect(routeArea({ meta: { area: "crm" } })).toBe("crm");
		expect(routeArea({ meta: {} })).toBe("home");
		expect(routeArea(undefined)).toBe("home");
	});

	it("labels navigation items, and falls back to the key", () => {
		const agent = personaFor(["SellOS Agent"]);
		expect(navLabel(agent, "home")).toBe("Home");
		expect(navLabel(agent, "unknown")).toBe("unknown");
	});
});
