import { apiRequest } from "../api";

// Partner registrations (SOS-P7-02). A partner of an approved firm registers a buyer and follows each
// registration. A Company Admin approves or rejects them and sets the programme's company settings.
const call = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.access.partner_registrations.${method}`,
		method: "POST",
		params,
	});

export const partnerRegistrationsApi = {
	form: () => call("partner_registration_form"),
	register: (values) => call("register_buyer", values),
	mine: () => call("my_partner_registrations"),
	list: () => call("list_partner_registrations"),
	approve: (name) => call("approve_partner_registration", { name }),
	reject: (name, reason) => call("reject_partner_registration", { name, reason }),
	settings: () => call("get_partner_settings"),
	saveSettings: (values) => call("save_partner_settings", values),
};
