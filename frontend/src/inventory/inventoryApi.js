import { apiRequest } from "../api";

// Developers, projects, units and properties (SOS-P4-01). Each call is one whitelisted method; the server
// checks the role and saves through the record's own checks.
const call = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.inventory.api.${method}`,
		method: "POST",
		params,
	});

export const inventoryApi = {
	overview: () => call("inventory_overview"),
	project: (name) => call("get_project", { name }),
	saveDeveloper: (values, name) => call("save_developer", { values, name }),
	saveProject: (values, name) => call("save_project", { values, name }),
	saveUnit: (values, name) => call("save_unit", { values, name }),
	saveProperty: (values, name) => call("save_property", { values, name }),
	setStatus: (doctype, name, status, reason = "") =>
		call("set_inventory_status", { doctype, name, status, reason }),
	setArchived: (doctype, name, archived) =>
		call("set_inventory_archived", { doctype, name, archived }),
};

// Towers, wings, floors, the units of a floor and a project's details (SOS-P7-05).
const structure = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.inventory.structure.${method}`,
		method: "POST",
		params,
	});

export const structureApi = {
	addTower: (project, tower_name, floors) =>
		structure("add_tower", { project, tower_name, floors }),
	addFloors: (tower, floors) => structure("add_floors", { tower, floors }),
	removeFloor: (tower, floor) => structure("remove_floor", { tower, floor }),
	removeTower: (tower) => structure("remove_tower", { tower }),
	generate: (values) => structure("generate_floor_units", values),
	saveDetails: (project, possession_date, amenities) =>
		structure("save_project_details", { project, possession_date, amenities }),
	saveAmenity: (amenity_name, archived = 0) =>
		structure("save_amenity", { amenity_name, archived }),
	addBrochure: (project, title, filename, content_base64) =>
		structure("add_project_brochure", { project, title, filename, content_base64 }),
	removeBrochure: (project, file) => structure("remove_project_brochure", { project, file }),
};

// The availability grid, holds and blocks (SOS-P7-06).
const holds = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.inventory.holds.${method}`,
		method: "POST",
		params,
	});

export const gridApi = {
	grid: (project, configuration = "", status = "") =>
		holds("unit_grid", { project, configuration, status }),
	hold: (unit, lead) => holds("hold_unit", { unit, lead }),
	release: (unit) => holds("release_hold", { unit }),
	block: (unit, reason) => holds("block_unit", { unit, reason }),
	unblock: (unit, reason) => holds("unblock_unit", { unit, reason }),
	saveHours: (unit_hold_hours) => holds("save_hold_settings", { unit_hold_hours }),
};

// One tone per status, for the badge.
export const STATUS_TONE = {
	Available: "success",
	Held: "warning",
	Booked: "info",
	Sold: "neutral",
	Blocked: "danger",
};
