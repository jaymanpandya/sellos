import { apiRequest } from "../api";

// The support access API (P1.13). Each call is one whitelisted method that only a company admin may call.
const call = (method, params = {}) =>
	apiRequest({ url: `/api/method/sellos.access.support.${method}`, method: "POST", params });

export const supportApi = {
	users: () => call("list_support_users"),
	grants: () => call("list_support_grants"),
	grant: (supportUser, durationMinutes, reason = "") =>
		call("grant_support_access", {
			support_user: supportUser,
			duration_minutes: durationMinutes,
			reason,
		}),
	revoke: (grant) => call("revoke_support_access", { grant }),
	log: (grant) => call("support_access_log", { grant }),
};

// The longest a grant may last is 4 hours. The server refuses anything longer.
export const DURATIONS = [
	{ minutes: 30, label: "30 minutes" },
	{ minutes: 60, label: "1 hour" },
	{ minutes: 120, label: "2 hours" },
	{ minutes: 240, label: "4 hours" },
];
