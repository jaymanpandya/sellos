import { apiRequest } from "../api";

// Micro markets, buildings and the building review (SOS-P3-04). Each call is one whitelisted method; the
// server checks the role and saves through the record's own checks.
const call = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.intel.buildings_api.${method}`,
		method: "POST",
		params,
	});

export const buildingsApi = {
	listMarkets: (includeArchived = 0) =>
		call("list_micro_markets", { include_archived: includeArchived }),
	saveMarket: (values, name = null) => call("save_micro_market", { name, values }),
	archiveMarket: (name, archived = 1) => call("set_micro_market_archived", { name, archived }),
	loadMarkets: () => call("load_micro_markets"),
	list: (params = {}) => call("list_buildings", params),
	get: (name) => call("get_building", { name }),
	save: (values, name = null) => call("save_building", { name, values }),
	correct: (name, values) => call("correct_building", { name, values }),
	confirm: (name) => call("confirm_building", { name }),
	loadSeedList: (text, microMarket = null, country = null) =>
		call("load_building_seed_list", { text, micro_market: microMarket, country }),
};
