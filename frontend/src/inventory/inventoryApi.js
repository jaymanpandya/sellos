import { apiRequest } from "../api";

// Developers, projects, units and properties (SOS-P4-01). Each call is one whitelisted method; the server
// checks the role and saves through the record's own checks.
const call = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.inventory.api.${method}`,
		method: "POST",
		params,
	});

export const inventoryApi = {
	overview: () => call("inventory_overview"),
	project: (name) => call("get_project", { name }),
	saveDeveloper: (values, name) => call("save_developer", { values, name }),
	saveProject: (values, name) => call("save_project", { values, name }),
	saveUnit: (values, name) => call("save_unit", { values, name }),
	saveProperty: (values, name) => call("save_property", { values, name }),
	setStatus: (doctype, name, status, reason = "") =>
		call("set_inventory_status", { doctype, name, status, reason }),
	setArchived: (doctype, name, archived) =>
		call("set_inventory_archived", { doctype, name, archived }),
};

// One tone per status, for the badge.
export const STATUS_TONE = { Available: "success", Held: "warning", Sold: "neutral" };
