import { apiRequest } from "../api";

// The setup wizard API (P1.03). Each call is one whitelisted method that only a company admin may call.
const call = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.config.setup_wizard.${method}`,
		method: "POST",
		params,
	});

export const setupApi = {
	state: () => call("get_setup_state"),
	saveProfile: (values) => call("save_profile", { values }),
	saveBranding: (brandColor, logoData = null, removeLogo = 0) =>
		call("save_branding", {
			brand_color: brandColor,
			...(logoData ? { logo_data: logoData } : {}),
			remove_logo: removeLogo,
		}),
	saveStages: (stages) => call("save_stages", { stages }),
	addUser: (email, firstName, role, lastName = "") =>
		call("add_user", { email, first_name: firstName, role, last_name: lastName }),
	finish: () => call("finish_setup"),
};

export const STEP_LABELS = {
	profile: "Company profile",
	branding: "Logo and colours",
	stages: "Pipeline stages",
	users: "First users",
};

export const ROLE_LABELS = {
	"SellOS Company Admin": "Company Admin",
	"SellOS Agent": "Agent",
	"SellOS Channel Partner": "Channel Partner",
};
