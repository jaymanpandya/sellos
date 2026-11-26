import { apiRequest } from "../api";

// DocuSeal signing of a mandate and the company profile (SOS-LOOP). Each call is one whitelisted method that checks
// the user's role. No call ever returns the API key or the webhook secret.
const call = (module, method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.inventory.${module}.${method}`,
		method: "POST",
		params,
	});

export const docusealApi = {
	status: () => call("docuseal", "docuseal_status"),
	settings: () => call("docuseal", "get_docuseal_settings"),
	saveSettings: (values) => call("docuseal", "save_docuseal_settings", { values }),
	check: () => call("docuseal", "check_docuseal_connection"),
	send: (name) => call("docuseal", "send_for_signing", { name }),
};

export const profileApi = {
	get: () => call("branding", "get_company_profile"),
	save: (values) => call("branding", "save_company_profile", { values }),
	uploadLogo: (filename, content_base64) =>
		call("branding", "upload_company_logo", { filename, content_base64 }),
};
