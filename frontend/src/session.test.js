import { beforeEach, describe, expect, it } from "vitest";

import { applyCompanyTheme, loadSession, session } from "./session";

beforeEach(() => {
	session.user = null;
	session.fullName = "";
	session.roles = [];
	session.company = { name: "", brandColor: "" };
	session.loaded = false;
	delete window.sellos_boot;
	delete window.boot;
	document.documentElement.removeAttribute("style");
});

describe("loadSession", () => {
	it("stays signed out when the page has no boot data", async () => {
		await loadSession();
		expect(session.user).toBeNull();
		expect(session.loaded).toBe(true);
	});

	it("treats the Guest user as signed out", async () => {
		window.sellos_boot = { user: "Guest" };
		await loadSession();
		expect(session.user).toBeNull();
	});

	it("fills the session from the boot data and applies the company colour", async () => {
		window.sellos_boot = {
			user: "agent@example.com",
			full_name: "A Agent",
			roles: ["SellOS Agent"],
			company: { name: "Pandya Realtors", brand_color: "#112233" },
		};
		await loadSession();
		expect(session.user).toBe("agent@example.com");
		expect(session.fullName).toBe("A Agent");
		expect(session.roles).toEqual(["SellOS Agent"]);
		expect(session.company.name).toBe("Pandya Realtors");
		expect(document.documentElement.style.getPropertyValue("--sos-brand")).toBe("#112233");
	});

	it("falls back to the email when the full name is missing", async () => {
		window.sellos_boot = { user: "agent@example.com" };
		await loadSession();
		expect(session.fullName).toBe("agent@example.com");
		expect(session.roles).toEqual([]);
	});
});

describe("applyCompanyTheme", () => {
	it("leaves the default colours alone when the company has none", () => {
		applyCompanyTheme({ name: "X", brandColor: "" });
		expect(document.documentElement.style.getPropertyValue("--sos-brand")).toBe("");
	});
});
