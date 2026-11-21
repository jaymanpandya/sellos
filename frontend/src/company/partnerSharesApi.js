import { apiRequest } from "../api";

// Sharing projects with channel partners (SOS-P7-03). A Company Admin shares a project, its units, its price
// list in force and chosen brochures with Approved firms, and withdraws a share. A partner reads only what is
// shared with their firm. Each call is one whitelisted method.
const call = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.inventory.partner_shares.${method}`,
		method: "POST",
		params,
	});

export const partnerSharesApi = {
	options: (project) => call("partner_share_options", project ? { project } : {}),
	list: (project) => call("list_partner_shares", project ? { project } : {}),
	share: ({ project, firms, units, sharePriceList, brochures }) =>
		call("share_project", {
			project,
			firms: JSON.stringify(firms),
			units: JSON.stringify(units),
			share_price_list: sharePriceList ? 1 : 0,
			brochures: JSON.stringify(brochures),
		}),
	withdraw: (name, reason) => call("withdraw_partner_share", { name, reason }),
	mine: () => call("my_shared_projects"),
	mineOne: (project) => call("my_shared_project", { project }),
};
