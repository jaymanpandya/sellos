import { apiRequest } from "../api";

// The call reports of a Company Admin (SOS-P2-11): the figures for a range of dates, and the calls behind
// one figure. A filter that is not set is left out, so the server does not filter by it. An empty agent is
// the calls that have no agent, so it is sent.
const call = (method, params = {}) =>
	apiRequest({ url: `/api/method/${method}`, method: "POST", params });

const clean = (values) =>
	Object.fromEntries(Object.entries(values).filter(([, v]) => v !== undefined && v !== null));

export const callsApi = {
	report: (range) => call("sellos.reports.calls.call_report", clean(range)),
	calls: (range, figure) =>
		call("sellos.reports.calls.call_report_calls", clean({ ...range, ...figure })),
};

// 125 seconds read as "2m 5s", and rupees as ₹3.00 in the Indian grouping.
export function talkTime(seconds) {
	const total = Math.round(seconds || 0);
	const hours = Math.floor(total / 3600);
	const minutes = Math.floor((total % 3600) / 60);
	const rest = total % 60;
	if (hours) return `${hours}h ${minutes}m`;
	return minutes ? `${minutes}m ${rest}s` : `${rest}s`;
}

export function rupees(value) {
	return `₹${Number(value || 0).toLocaleString("en-IN", {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	})}`;
}
