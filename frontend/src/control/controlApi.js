import { apiRequest } from "../api";

// The control site API (P1.01). It uses the framework's document methods, which check the signed in
// user's permission on each DocType. Only a Platform Admin holds it, so a company user gets a 403.
const call = (method, params = {}) =>
	apiRequest({ url: `/api/method/${method}`, method: "POST", params });

const TENANT_FIELDS = [
	"name",
	"tenant_id",
	"company_name",
	"status",
	"plan",
	"admin_email",
	"site_name",
];

// The order a status may change in. The server enforces it too and refuses anything else.
export const NEXT_STATUSES = {
	Requested: ["Provisioning"],
	Provisioning: ["Active", "Failed"],
	Active: [],
	Failed: ["Provisioning"],
};

export const controlApi = {
	tenants: () =>
		call("frappe.client.get_list", {
			doctype: "Tenant",
			fields: TENANT_FIELDS,
			order_by: "creation desc",
			limit_page_length: 0,
		}),
	plans: () =>
		call("frappe.client.get_list", {
			doctype: "Plan",
			fields: ["name"],
			filters: { enabled: 1 },
			order_by: "name asc",
			limit_page_length: 0,
		}),
	jobs: () =>
		call("frappe.client.get_list", {
			doctype: "Provisioning Job",
			fields: ["name", "tenant", "status", "attempts"],
			order_by: "creation desc",
			limit_page_length: 0,
		}),
	createTenant: (values) =>
		call("frappe.client.insert", { doc: { doctype: "Tenant", ...values } }),
	setTenantStatus: (name, status) =>
		call("frappe.client.set_value", {
			doctype: "Tenant",
			name,
			fieldname: "status",
			value: status,
		}),
};
