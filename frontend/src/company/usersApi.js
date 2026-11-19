import { apiRequest } from "../api";

// The Company Admin's user management API (SOS-P1-17). Each call is one whitelisted method that only a
// Company Admin may call.
const call = (method, params = {}) =>
	apiRequest({ url: `/api/method/sellos.access.users.${method}`, method: "POST", params });

export const usersApi = {
	list: () => call("list_users"),
	invite: (values) => call("invite_user", values),
	resend: (email) => call("resend_invitation", { email }),
	save: (email, values) => call("save_user", { email, values }),
	// SOS-P1-19: an agent with open work needs `reassignTo` (an agent) or `distribute` (the team shares it).
	deactivate: (email, { reassignTo = null, distribute = 0 } = {}) =>
		call("deactivate_user", { email, reassign_to: reassignTo, distribute }),
	reactivate: (email) => call("reactivate_user", { email }),
};
