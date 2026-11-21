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

// Price lists, payment plans and the company's percentages (SOS-P7-07).
const pricing = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.inventory.pricing.${method}`,
		method: "POST",
		params,
	});

export const pricingApi = {
	project: (project) => pricing("project_pricing", { project }),
	savePriceList: (project, values) => pricing("save_price_list", { project, values }),
	savePlan: (project, values, name) => pricing("save_payment_plan", { project, values, name }),
	archivePlan: (name, archived = 1) => pricing("archive_payment_plan", { name, archived }),
	saveRates: (stamp_duty_percent, registration_percent, gst_percent) =>
		pricing("save_cost_settings", { stamp_duty_percent, registration_percent, gst_percent }),
};

// Cost sheets of a unit (SOS-P7-07).
const sheets = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.inventory.cost_sheet.${method}`,
		method: "POST",
		params,
	});

export const costSheetApi = {
	options: (unit) => sheets("cost_sheet_options", { unit }),
	make: (unit, payment_plan, optional_charges) =>
		sheets("make_cost_sheet", { unit, payment_plan, optional_charges }),
	get: (name) => sheets("get_cost_sheet", { name }),
	pdfUrl: (name) =>
		`/api/method/sellos.inventory.cost_sheet.cost_sheet_pdf?name=${encodeURIComponent(name)}`,
};

// Rupees with Indian grouping: 10155600 is Rs 1,01,55,600.
export const rupees = (n) =>
	`Rs ${new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(Number(n || 0))}`;

// Listings: Primary, Direct or Partner, published only when complete (SOS-P4-02).
const listing = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.inventory.listings.${method}`,
		method: "POST",
		params,
	});

export const listingApi = {
	overview: (include_archived = 0) => listing("listing_overview", { include_archived }),
	save: (values, name) => listing("save_listing", { values, name }),
	publish: (name) => listing("publish_listing", { name }),
	unpublish: (name) => listing("unpublish_listing", { name }),
	setArchived: (name, archived) => listing("set_listing_archived", { name, archived }),
};

// Photos and videos of a listing, from the company's asset library (SOS-P4-03).
const media = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.inventory.media.${method}`,
		method: "POST",
		params,
	});

export const mediaApi = {
	get: (listing) => media("listing_media", { listing }),
	upload: (listing, title, filename, content_base64) =>
		media("upload_listing_media", { listing, title, filename, content_base64 }),
	link: (listing, media_asset) => media("link_listing_media", { listing, media_asset }),
	unlink: (listing, media_asset) => media("unlink_listing_media", { listing, media_asset }),
	reorder: (listing, order) => media("reorder_listing_media", { listing, order }),
};

// One tone per status, for the badge.
export const STATUS_TONE = {
	Available: "success",
	Held: "warning",
	Booked: "info",
	Sold: "neutral",
	Blocked: "danger",
};

// Matching buyers to units and listings, and the weights of the score (SOS-P7-08).
const matching = (method, params = {}) =>
	apiRequest({
		url: `/api/method/sellos.inventory.matching.${method}`,
		method: "POST",
		params,
	});

export const matchApi = {
	forLead: (lead) => matching("matches_for_lead", { lead }),
	forUnit: (unit) => matching("leads_for_unit", { unit }),
	forListing: (listing) => matching("leads_for_listing", { listing }),
	settings: () => matching("get_match_settings"),
	saveSettings: (weights) => matching("save_match_settings", weights),
};

// One tone per score: 70 and over is a good match, 40 and over a fair one.
export const scoreTone = (score) =>
	score >= 70 ? "success" : score >= 40 ? "warning" : "neutral";
