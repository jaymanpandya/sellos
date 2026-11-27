import { apiRequest } from "../api";

// The Integrations screen (SOS-INT-1). Each call is one whitelisted method that only a Company Admin may call. No call
// returns a secret: a saved one comes back as "Saved, ending xxxx" in the field's `saved`.
const call = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.config.integrations.${method}`,
		method: "POST",
		params,
	});

export const integrationsApi = {
	list: () => call("list_integrations"),
	save: (provider, values) => call("save_integration", { provider, values }),
	check: (provider) => call("check_integration", { provider }),
};
