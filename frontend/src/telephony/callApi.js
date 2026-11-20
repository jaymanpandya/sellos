import { apiRequest } from "../api";

// The click to call API (SOS-P2-07). Each call is one whitelisted method for an Agent, a Sales Manager or a
// Company Admin. Nothing here returns the lead's phone number.
const call = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.telephony.click_to_call.${method}`,
		method: "POST",
		params,
	});

export const callApi = {
	preview: (lead, purpose = "Service") => call("call_preview", { lead, purpose }),
	start: (lead, purpose = "Service") => call("click_to_call", { lead, purpose }),
	status: (callLog) => call("call_status", { call_log: callLog }),
	pending: () => call("pending_outcomes"),
	recordOutcome: (callLog, values) => call("record_outcome", { call_log: callLog, ...values }),
};
