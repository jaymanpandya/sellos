import { apiRequest } from "../api";

// Commission rates, payouts and statements (SOS-P7-04). Each call is one whitelisted method that checks the
// user's role: a Company Admin sets rates, moves payouts and exports; a partner reads only their own statement.
const call = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.inventory.commissions.${method}`,
		method: "POST",
		params,
	});

const clean = (values) =>
	Object.fromEntries(
		Object.entries(values).filter(([, v]) => v !== undefined && v !== null && v !== "")
	);

export const commissionApi = {
	overview: (include_archived = 0) => call("commission_overview", { include_archived }),
	saveRate: (values) => call("save_commission_rate", { values }),
	setRateArchived: (name, archived) => call("set_commission_rate_archived", { name, archived }),
	createMissing: () => call("create_missing_payouts"),
	move: (name, to, extra = {}) => call("move_payout", clean({ name, to, ...extra })),
	exportStatement: (firm, range) => call("export_partner_statement", clean({ firm, ...range })),
	partnerStatement: (range) => call("partner_commission", clean({ ...range })),
};
