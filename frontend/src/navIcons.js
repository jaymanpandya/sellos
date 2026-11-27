// Lucide icons (frappe-ui's set, the one BuildOS and PAMAA use) by menu key. Every menu key has one
// (docs/UI_STANDARD.md); the visual walk through fails on a nav item with no icon.
export const ICONS = {
	home: "lucide-layout-dashboard",
	leads: "lucide-users",
	queue: "lucide-phone-call",
	visits: "lucide-map-pinned",
	import: "lucide-file-up",
	sellers: "lucide-user-round-check",
	mandates: "lucide-file-signature",
	deals: "lucide-handshake",
	inventory: "lucide-building",
	"inventory-import": "lucide-package-plus",
	"business-reports": "lucide-briefcase",
	partners: "lucide-heart-handshake",
	registrations: "lucide-clipboard-list",
	firm: "lucide-store",
	register: "lucide-user-plus",
	agent: "lucide-contact",
	client: "lucide-contact",
	overview: "lucide-scroll-text",
	shortlists: "lucide-bookmark",
	users: "lucide-user-cog",
	support: "lucide-life-buoy",
	integrations: "lucide-plug",
	telephony: "lucide-phone",
	whatsapp: "lucide-message-circle",
	"whatsapp-setup": "lucide-message-circle-more",
	"response-alerts": "lucide-timer",
	"call-lists": "lucide-list-checks",
	teams: "lucide-users-round",
	assignment: "lucide-shuffle",
	"call-reports": "lucide-phone-call",
	reports: "lucide-chart-column",
	"team-report": "lucide-chart-column",
	tenants: "lucide-building-2",
	"platform-reports": "lucide-chart-column",
	results: "lucide-chart-column",
	commission: "lucide-hand-coins",
	earnings: "lucide-wallet",
	shares: "lucide-share-2",
	shared: "lucide-building-2",
};

// The sidebar groups (docs/UI_STANDARD.md, "Sidebar"): each has an icon and a small caps label, and
// remembers whether it is open. `GROUP_OF` puts a menu key in a group; the partner, platform and client
// areas are groups of their own. A key not listed here stays under "Company".
export const GROUPS = [
	{ key: "work", label: "Work", icon: "lucide-briefcase" },
	{ key: "sales", label: "Sales", icon: "lucide-trending-up" },
	{ key: "inventory", label: "Inventory", icon: "lucide-building" },
	{ key: "data", label: "Data", icon: "lucide-database" },
	{ key: "reports", label: "Reports", icon: "lucide-chart-column" },
	{ key: "company", label: "Company", icon: "lucide-building-2" },
	{ key: "platform", label: "Platform", icon: "lucide-server" },
	{ key: "partner", label: "Partner", icon: "lucide-heart-handshake" },
	{ key: "client", label: "Your account", icon: "lucide-contact" },
];

export const GROUP_OF = {
	leads: "work",
	queue: "work",
	visits: "work",
	whatsapp: "work",
	"call-lists": "work",
	"response-alerts": "work",
	sellers: "sales",
	mandates: "sales",
	deals: "sales",
	commission: "sales",
	inventory: "inventory",
	"inventory-import": "inventory",
	import: "data",
	"call-reports": "reports",
	"business-reports": "reports",
	"team-report": "reports",
	reports: "reports",
	users: "company",
	support: "company",
};

// The group of a menu item of a persona: its area decides for the three areas that are groups of their own.
export function groupOf(item) {
	if (item.area === "platform") return "platform";
	if (item.area === "partner") return "partner";
	if (item.area === "client") return "client";
	return GROUP_OF[item.key] || "company";
}
