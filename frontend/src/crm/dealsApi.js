import { apiRequest } from "../api";

// Deals and their commission split (SOS-P4-06). Each call is one whitelisted method that checks the user's
// role: only a Company Admin may call any of them.
const call = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.inventory.deals.${method}`,
		method: "POST",
		params,
	});

export const dealApi = {
	overview: (include_archived = 0) => call("deal_overview", { include_archived }),
	save: (values, name = null) => call("save_deal", { values, name }),
	approve: (name) => call("approve_splits", { name }),
	reopen: (name) => call("reopen_splits", { name }),
	setArchived: (name, archived) => call("set_deal_archived", { name, archived }),
};
