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
