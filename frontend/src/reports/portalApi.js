import { apiRequest } from "../api";

// The Channel Partner's own report and the Platform Admin's reports (SOS-P5-03). A date that is not set is
// left out, so the server uses the last 30 days.
const call = (method, params = {}) =>
	apiRequest({ url: `/api/method/${method}`, method: "POST", params });

const clean = (values) =>
	Object.fromEntries(
		Object.entries(values).filter(([, v]) => v !== undefined && v !== null && v !== "")
	);

export const partnerReportApi = {
	run: (range) => call("sellos.reports.partner.partner_report", clean({ ...range })),
};

export const platformReportApi = {
	list: () => call("sellos.reports.platform.list_platform_reports"),
	run: (report, range) =>
		call("sellos.reports.platform.run_platform_report", clean({ report, ...range })),
};
