import { apiRequest } from "../api";

// The CRM API (P1.06). Each call is one whitelisted method that checks the user's role. The request
// helper returns the method's own return value, not the {message: ...} wrapper (SOS-P1-06A).
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
