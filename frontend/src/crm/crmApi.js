import { apiRequest } from "../api";

// The CRM API (P1.06). Each call is one whitelisted method that checks the user's role.
const call = (method, params = {}) =>
	apiRequest({ url: `/api/method/sellos.crm.api.${method}`, method: "POST", params });

export const crmApi = {
	listLeads: (search = "", includeArchived = 0) =>
		call("list_leads", { search, include_archived: includeArchived }),
	getLead: (name) => call("get_lead", { name }),
	saveClient: (values, name = null) => call("save_client", { name, values }),
	saveLead: (values, name = null) => call("save_lead", { name, values }),
	addActivity: (lead, activityType, notes = "") =>
		call("add_activity", { lead, activity_type: activityType, notes }),
	saveTask: (values, name = null) => call("save_task", { name, values }),
	saveSiteVisit: (values, name = null) => call("save_site_visit", { name, values }),
	setArchived: (doctype, name, archived = 1) =>
		call("set_archived", { doctype, name, archived }),
};

export const CLIENT_TYPES = ["Buyer", "Seller", "Investor", "NRI"];
export const ACTIVITY_TYPES = ["Call", "WhatsApp", "Email", "Meeting", "Note"];
