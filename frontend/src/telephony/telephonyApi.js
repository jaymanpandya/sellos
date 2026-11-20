import { apiRequest } from "../api";

// The Telephony Settings API (SOS-P2-01). Each call is one whitelisted method that only a company admin
// may call. No call returns a key: the server says only whether each key is set.
const call = (method, params = {}) =>
	apiRequest({ url: `/api/method/sellos.telephony.settings.${method}`, method: "POST", params });

export const telephonyApi = {
	get: () => call("get_telephony_settings"),
	save: ({ authId, authToken, phoneNumber }) =>
		call("save_telephony_settings", {
			auth_id: authId,
			auth_token: authToken,
			phone_number: phoneNumber,
		}),
	check: () => call("check_connection"),
};

// Calling hours and the do not call list (SOS-P2-10), for the Company Admin.
const rules = (module, method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.telephony.${module}.${method}`,
		method: "POST",
		params,
	});

export const callingRulesApi = {
	getHours: () => rules("hours", "get_calling_hours"),
	saveHours: ({ enabled, start, end, days }) =>
		rules("hours", "save_calling_hours", {
			enabled: enabled ? 1 : 0,
			start,
			end,
			days: days.join(","),
		}),
	importList: (text) => rules("dnd", "import_do_not_call_list", { text }),
	summary: () => rules("dnd", "do_not_call_summary"),
};
