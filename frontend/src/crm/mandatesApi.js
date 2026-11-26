import { apiRequest } from "../api";

// Mandates and their Private Sale Dossier (SOS-P4-05). Each call is one whitelisted method that checks the
// user's role. The Dossier is released by the server only for a signed mandate.
const call = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.inventory.mandates.${method}`,
		method: "POST",
		params,
	});

export const mandateApi = {
	overview: (include_archived = 0) => call("mandate_overview", { include_archived }),
	save: (values, name = null) => call("save_mandate", { values, name }),
	sign: (name, filename, content_base64) =>
		call("sign_mandate", { name, filename, content_base64 }),
	addNote: (name, title, note) => call("add_dossier_note", { name, title, note }),
	addFile: (name, title, filename, content_base64) =>
		call("add_dossier_file", { name, title, filename, content_base64 }),
	openDossier: (name) => call("open_dossier", { name }),
	status: (leads) => call("mandate_status", { leads }),
	generateDossierPdf: (name) => call("generate_dossier_pdf", { name }),
	setArchived: (name, archived) => call("set_mandate_archived", { name, archived }),
};
