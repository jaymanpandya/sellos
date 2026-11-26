import { apiRequest } from "../api";

// Notes on a lead, a seller and a mandate (SOS-LOOP). Each call is one whitelisted method judged on the record.
const call = (method, params = {}) =>
	apiRequest({ url: `/api/method/sellos.crm.notes.${method}`, method: "POST", params });

export const notesApi = {
	list: (params) => call("list_notes", params),
	add: (params) => call("add_note", params),
	update: (params) => call("update_note", params),
	remove: (name) => call("delete_note", { name }),
	types: () => call("note_types"),
	typeSettings: () => call("note_type_settings"),
	saveType: (label, name = null, enabled = 1) =>
		call("save_note_type", { label, name, enabled }),
};
