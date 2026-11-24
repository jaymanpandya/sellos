// The SellOS areas (docs/DESIGN_SYSTEM.md, "Areas"). The colours and icons are defined once, in
// theme/ui-tokens.js; this file says which area a menu item and a route belong to, and the sidebar, the page
// header, the stat tiles and the empty states ask it.
import { areas } from "./theme/ui-tokens.js";

export { areas };
export const AREA_ORDER = ["sales", "calls", "inventory", "money", "company"];

// Menu key to area. A key not listed belongs to Company.
const AREA_OF_KEY = {
	home: "sales",
	leads: "sales",
	sellers: "sales",
	mandates: "sales",
	deals: "sales",
	import: "sales",
	overview: "sales",
	shortlists: "sales",
	firm: "sales",
	register: "sales",
	shared: "sales",
	queue: "calls",
	whatsapp: "calls",
	visits: "calls",
	"call-lists": "calls",
	"response-alerts": "calls",
	inventory: "inventory",
	"inventory-import": "inventory",
	commission: "money",
	earnings: "money",
	results: "money",
	reports: "money",
	"business-reports": "money",
	"call-reports": "money",
	"team-report": "money",
	"platform-reports": "money",
};

export const areaOfItem = (item) => AREA_OF_KEY[item.key] || "company";

// Route area (meta.area in router.js) to area, for a page that is not a menu item (a lead page, a project page).
const AREA_OF_ROUTE = {
	home: "sales",
	crm: "sales",
	client: "sales",
	partner: "sales",
	inventory: "inventory",
	reports: "money",
	insights: "money",
	company: "company",
	platform: "company",
	profile: "company",
};

// The area of the open page: the menu item whose path is the longest prefix of the path, else the route's area.
export function areaKeyFor(path, route, items = []) {
	let best = null;
	for (const item of items) {
		const p = item.to === "/" ? null : item.to;
		if (p && (path === p || path.startsWith(`${p}/`)) && (!best || p.length > best.to.length))
			best = item;
	}
	if (best) return areaOfItem(best);
	if (path === "/" || path === "") return "sales";
	return AREA_OF_ROUTE[route?.meta?.area] || "sales";
}
