import { apiRequest } from "../api";

// The Company Admin's business reports (SOS-P5-02): the funnel, source performance, agent productivity and
// listing and mandate ageing, each for a range of dates. A date that is not set is left out.
const call = (method, params = {}) =>
	apiRequest({ url: `/api/method/${method}`, method: "POST", params });

const clean = (values) =>
	Object.fromEntries(
		Object.entries(values).filter(([, v]) => v !== undefined && v !== null && v !== "")
	);

export const businessApi = {
	funnel: (range) => call("sellos.reports.standard.lead_funnel", clean(range)),
	sources: (range) => call("sellos.reports.standard.source_performance", clean(range)),
	agents: (range) => call("sellos.reports.standard.agent_productivity", clean(range)),
	ageing: (range) => call("sellos.reports.standard.ageing_report", clean(range)),
};
