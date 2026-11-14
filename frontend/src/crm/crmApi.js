import { apiRequest } from "../api";

// The CRM API (P1.06). Each call is one whitelisted method that checks the user's role. The request
// helper returns the method's own return value, not the {message: ...} wrapper (SOS-P1-06A).
const call = (method, params = {}) =>
	apiRequest({ url: `/api/method/sellos.crm.api.${method}`, method: "POST", params });

export const crmApi = {
	listLeads: (search = "", includeArchived = 0, filters = {}) =>
		call("list_leads", { search, include_archived: includeArchived, ...filters }),
	getLead: (name) => call("get_lead", { name }),
	findDuplicates: (values) => call("find_duplicates", values),
	mergeClients: (keep, merge) => call("merge_clients", { keep, merge }),
	listClients: (search = "") => call("list_clients", { search }),
	saveClient: (values, name = null) => call("save_client", { name, values }),
	saveLead: (values, name = null) => call("save_lead", { name, values }),
	addActivity: (lead, activityType, notes = "") =>
		call("add_activity", { lead, activity_type: activityType, notes }),
	saveTask: (values, name = null) => call("save_task", { name, values }),
	saveSiteVisit: (values, name = null) => call("save_site_visit", { name, values }),
	recordConsent: (lead, basis, evidenceLink) =>
		call("record_consent", { lead, basis, evidence_link: evidenceLink }),
	recordOptOut: (lead, source) => call("record_opt_out", { lead, source }),
	recordDndResult: (lead, registered = 1) => call("record_dnd_result", { lead, registered }),
	setArchived: (doctype, name, archived = 1) =>
		call("set_archived", { doctype, name, archived }),
};

export const CLIENT_TYPES = ["Buyer", "Seller", "Investor", "NRI"];
export const CONSENT_BASES = ["Consent", "Inquiry", "Application"];
export const STOP_SOURCES = [
	"Phone call",
	"WhatsApp",
	"SMS",
	"Email",
	"In person",
	"Website",
	"Other",
];
// What a buyer wants (SOS-P1-15). The server checks every choice against the same lists.
export const CONFIGURATIONS = ["1 RK", "1 BHK", "2 BHK", "3 BHK", "4 BHK and above"];
export const PROPERTY_TYPES = ["Apartment", "Villa", "Plot", "Office", "Shop"];
export const PURPOSES = ["End use", "Investment"];
export const TIMELINES = ["Immediate", "Within 3 months", "3 to 6 months", "Over 6 months"];
export const POSSESSIONS = ["Ready", "Under construction", "Any"];
export const ACTIVITY_TYPES = ["Call", "WhatsApp", "Email", "Meeting", "Note"];

// The message the server sent for a failed call, or the fallback. The request helper puts the
// server's messages in error.messages as plain text. The product framework name is never shown.
export function serverMessage(error, fallback) {
	const messages = (error?.messages || []).map((m) =>
		String(m)
			.replace(/<[^>]*>/g, "")
			.trim()
	);
	const text = messages.find((m) => m && m !== "Internal Server Error" && !/frappe/i.test(m));
	if (text) return text;
	if (error?.response?.status === 403) return "You do not have permission to do this.";
	return fallback;
}
