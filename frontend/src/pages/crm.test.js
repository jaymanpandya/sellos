import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { crmApi } from "../crm/crmApi";
import { createAppRouter } from "../router";
import { session } from "../session";
import LeadPage from "./LeadPage.vue";
import LeadsPage from "./LeadsPage.vue";

vi.mock("../crm/crmApi", () => ({
	CLIENT_TYPES: ["Buyer", "Seller", "Investor", "NRI"],
	ACTIVITY_TYPES: ["Call", "WhatsApp", "Email", "Meeting", "Note"],
	crmApi: {
		listLeads: vi.fn(),
		getLead: vi.fn(),
		saveClient: vi.fn(),
		saveLead: vi.fn(),
		addActivity: vi.fn(),
		saveTask: vi.fn(),
		saveSiteVisit: vi.fn(),
		setArchived: vi.fn(),
	},
}));

const lead = (timeline = []) => ({
	message: {
		lead: { name: "LD-1" },
		client: { client_name: "Asha Rao", client_type: "Buyer", phone: "*********345" },
		timeline,
	},
});

async function mountAt(path, component, area) {
	const router = createAppRouter();
	await router.push(path);
	await router.isReady();
	void area;
	const wrapper = mount(component, { global: { plugins: [router] } });
	await flushPromises();
	return { wrapper, router };
}

beforeEach(() => {
	vi.clearAllMocks();
	session.roles = ["SellOS Agent"];
	crmApi.listLeads.mockResolvedValue({ message: [] });
});

describe("CRM routes", () => {
	async function name(path, roles) {
		session.roles = roles;
		const router = createAppRouter();
		await router.push(path);
		await router.isReady();
		return router.currentRoute.value.name;
	}

	it("lets agents and company admins open the leads", async () => {
		expect(await name("/crm/leads", ["SellOS Agent"])).toBe("leads");
		expect(await name("/crm/leads/LD-1", ["SellOS Company Admin"])).toBe("lead");
	});

	it("keeps partners, clients and the platform admin out of the CRM area", async () => {
		for (const role of ["SellOS Channel Partner", "SellOS Client", "SellOS Platform Admin"]) {
			expect(await name("/crm/leads", [role]), role).toBe("no-access");
		}
	});

	it("gives partners their own leads route and nobody else", async () => {
		expect(await name("/partner/leads", ["SellOS Channel Partner"])).toBe("partner-leads");
		expect(await name("/partner/leads", ["SellOS Agent"])).toBe("no-access");
		expect(await name("/partner/leads", ["SellOS Client"])).toBe("no-access");
	});
});

describe("leads page", () => {
	it("lists leads and shows overdue tasks", async () => {
		crmApi.listLeads.mockResolvedValue({
			message: [
				{ name: "LD-1", client_name: "Asha Rao", source: "Website", overdue_tasks: 2 },
			],
		});
		const { wrapper } = await mountAt("/crm/leads", LeadsPage);
		expect(wrapper.text()).toContain("Asha Rao");
		expect(wrapper.text()).toContain("2 overdue");
	});

	it("creates a client and a lead, then opens the lead", async () => {
		crmApi.saveClient.mockResolvedValue({ message: { name: "CL-1" } });
		crmApi.saveLead.mockResolvedValue({ message: { lead: { name: "LD-1" } } });
		const { wrapper, router } = await mountAt("/crm/leads", LeadsPage);
		await wrapper.find("button").trigger("click");
		await wrapper.find('input[placeholder="Client name"]').setValue("Asha Rao");
		await wrapper.find('input[placeholder="Source"]').setValue("Website");
		await wrapper.find("form").trigger("submit");
		await flushPromises();
		expect(crmApi.saveClient).toHaveBeenCalledWith(
			expect.objectContaining({ client_name: "Asha Rao", client_type: "Buyer" })
		);
		expect(crmApi.saveLead).toHaveBeenCalledWith({ client: "CL-1", source: "Website" });
		expect(router.currentRoute.value.fullPath).toBe("/crm/leads/LD-1");
	});
});

describe("lead page", () => {
	it("logs an activity and reloads the timeline", async () => {
		crmApi.getLead.mockResolvedValueOnce(lead()).mockResolvedValueOnce(
			lead([
				{
					kind: "activity",
					name: "A1",
					title: "Call",
					when: "2026-11-04 10:00:00",
					notes: "intro",
				},
			])
		);
		crmApi.addActivity.mockResolvedValue({ message: {} });
		const { wrapper } = await mountAt("/crm/leads/LD-1", LeadPage);
		expect(wrapper.text()).toContain("*********345");
		expect(wrapper.text()).toContain("Nothing logged yet");
		await wrapper.find('input[placeholder="Notes"]').setValue("intro");
		await wrapper.findAll("form")[0].trigger("submit");
		await flushPromises();
		expect(crmApi.addActivity).toHaveBeenCalledWith("LD-1", "Call", "intro");
		expect(wrapper.text()).toContain("intro");
	});

	it("marks an overdue task", async () => {
		crmApi.getLead.mockResolvedValue(
			lead([
				{
					kind: "task",
					name: "T1",
					title: "Send brochure",
					when: "2026-11-01",
					status: "Open",
					overdue: true,
				},
			])
		);
		const { wrapper } = await mountAt("/crm/leads/LD-1", LeadPage);
		expect(wrapper.text()).toContain("Overdue");
	});

	it("shows a partner the timeline but no way to log or archive", async () => {
		session.roles = ["SellOS Channel Partner"];
		crmApi.getLead.mockResolvedValue(
			lead([{ kind: "activity", name: "A1", title: "Call", when: "2026-11-04 10:00:00" }])
		);
		const { wrapper } = await mountAt("/partner/leads/LD-1", LeadPage);
		expect(wrapper.text()).toContain("Call");
		expect(wrapper.text()).not.toContain("Add activity");
		expect(wrapper.text()).not.toContain("Archive");
	});
});
