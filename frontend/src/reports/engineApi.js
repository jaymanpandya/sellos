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

// Saved views, export and scheduled email (SOS-P5-04). A view holds filters only. An export is a report
// result as a file, for a Company Admin; the answer holds the file (base64) and the rows it was made from.
export const exportsApi = {
	views: () => call("sellos.reports.exports.list_report_views"),
	saveView: (values, view) =>
		call(
			"sellos.reports.exports.save_report_view",
			clean({ values: JSON.stringify(values), view })
		),
	deleteView: (view) => call("sellos.reports.exports.delete_report_view", { view }),
	exportReport: (report, range, format) =>
		call("sellos.reports.exports.export_report", clean({ report, ...range, format })),
	schedules: () => call("sellos.reports.exports.list_report_schedules"),
	saveSchedule: (values, schedule) =>
		call(
			"sellos.reports.exports.save_report_schedule",
			clean({ values: JSON.stringify(values), schedule })
		),
	deleteSchedule: (schedule) =>
		call("sellos.reports.exports.delete_report_schedule", { schedule }),
	sendSchedule: (schedule) =>
		call("sellos.reports.exports.send_report_schedule_now", { schedule }),
};

// Hand the file of an export to the browser.
export function saveFile(result) {
	const bytes = Uint8Array.from(atob(result.content), (c) => c.charCodeAt(0));
	const link = document.createElement("a");
	link.href = URL.createObjectURL(new Blob([bytes], { type: result.mime }));
	link.download = result.filename;
	link.click();
	URL.revokeObjectURL(link.href);
}
