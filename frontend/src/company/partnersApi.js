import { apiRequest } from "../api";

// Channel partner firms (SOS-P7-01). A Company Admin invites, corrects, approves, suspends and reinstates
// firms. A partner reads its own firm's state and completes its details. Each call is one whitelisted method.
const call = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.access.partner_firms.${method}`,
		method: "POST",
		params,
	});

// A chosen file as base64, for the signed agreement.
export function readFileBase64(file) {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
		reader.onerror = () => reject(new Error("The file could not be read."));
		reader.readAsDataURL(file);
	});
}

export const partnersApi = {
	list: () => call("list_partner_firms"),
	invite: (values) => call("invite_partner_firm", values),
	update: (name, values) => call("update_partner_firm", { name, values }),
	approve: (name) => call("approve_partner_firm", { name }),
	suspend: (name, reason) => call("suspend_partner_firm", { name, reason }),
	reinstate: (name) => call("reinstate_partner_firm", { name }),
	uploadAgreement: (name, filename, contentBase64) =>
		call("upload_agreement_for_firm", { name, filename, content_base64: contentBase64 }),
	mine: () => call("my_partner_firm"),
	submitDetails: (values) => call("submit_partner_details", { values }),
	uploadMyAgreement: (filename, contentBase64) =>
		call("upload_my_agreement", { filename, content_base64: contentBase64 }),
};
