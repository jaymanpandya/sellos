import { beforeEach, describe, expect, it } from "vitest";

import { createAppRouter } from "./router";
import { session } from "./session";

async function open(path) {
	const router = createAppRouter();
	await router.push(path);
	await router.isReady();
	return router.currentRoute.value;
}

beforeEach(() => {
	session.roles = [];
});

describe("route access", () => {
	it("sends a user without a SellOS role to the no access page", async () => {
		expect((await open("/")).name).toBe("no-access");
	});

	it("lets every SellOS role open the home page", async () => {
		for (const role of [
			"SellOS Platform Admin",
			"SellOS Company Admin",
			"SellOS Agent",
			"SellOS Channel Partner",
			"SellOS Client",
		]) {
			session.roles = [role];
			expect((await open("/")).name, role).toBe("home");
		}
	});

	it("always lets a user reach the no access page itself", async () => {
		expect((await open("/no-access")).name).toBe("no-access");
	});
});
