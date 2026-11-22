import { apiRequest } from "../api";

// The report engine (SOS-P5-01): the reports a person may open, one report's figures for a range of
// dates, the records behind a figure, and (Company Admin) the nightly table's refresh. A filter that is not
// set is left out. An empty group is a real group (the records with no value), so it is sent.
const call = (method, params = {}) =>
	apiRequest({ url: `/api/method/${method}`, method: "POST", params });

const clean = (values) =>
	Object.fromEntries(Object.entries(values).filter(([, v]) => v !== undefined && v !== null));

export const reportsApi = {
	list: () => call("sellos.reports.engine.list_reports"),
	run: (report, range) => call("sellos.reports.engine.run_report", clean({ report, ...range })),
	records: (report, range, group) =>
		call("sellos.reports.engine.report_records", clean({ report, ...range, group })),
	refresh: (report) => call("sellos.reports.engine.refresh_report", clean({ report })),
};
