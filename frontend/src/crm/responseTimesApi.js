import { apiRequest } from "../api";

// The response time limits (SOS-P7-13). Each call is one whitelisted method for a Company Admin.
const call = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.crm.response_times.${method}`,
		method: "POST",
		params,
	});

export const responseTimesApi = {
	get: () => call("get_response_limits"),
	save: ({ unassignedMinutes, contactMinutes }) =>
		call("save_response_limits", {
			unassigned_minutes: unassignedMinutes,
			contact_minutes: contactMinutes,
		}),
};
