// Shared display formats (docs/UI_STANDARD.md).
const MONTHS = [
	"Jan",
	"Feb",
	"Mar",
	"Apr",
	"May",
	"Jun",
	"Jul",
	"Aug",
	"Sep",
	"Oct",
	"Nov",
	"Dec",
];

// A server timestamp such as "2026-11-24 11:44:44.464787" as "24 Nov 2026, 11:44". The parts are read from
// the text, so the site's own time shows and the browser's time zone cannot move it. Anything that is not
// a timestamp comes back unchanged, so no value is ever lost.
export function formatDateTime(value) {
	const match = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(String(value ?? ""));
	if (!match) return value ?? "";
	const [, year, month, day, hour, minute] = match;
	return `${Number(day)} ${MONTHS[Number(month) - 1]} ${year}, ${hour}:${minute}`;
}

// A date alone, "24 Nov 2026", from a server date or timestamp. Anything else comes back unchanged.
export function formatDate(value) {
	const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value ?? ""));
	if (!match) return value ?? "";
	const [, year, month, day] = match;
	return `${Number(day)} ${MONTHS[Number(month) - 1]} ${year}`;
}

// A day and, when the value has one, its time: "24 Nov 2026, 11:44". A date with no time shows as a date.
export function formatWhen(value) {
	const text = String(value ?? "");
	const time = /[ T](\d{2}:\d{2})/.exec(text);
	if (!time || time[1] === "00:00") return formatDate(text);
	return formatDateTime(text);
}

// MONEY (docs/DESIGN_SYSTEM.md, "Money"): one format everywhere, "Rs", no paise, never the rupee sign.
// formatBudget is the default, for every figure that is read at a glance: 23000000 is "Rs 2.3 crore",
// 8500000 is "Rs 85 lakh", and below a lakh the full amount with Indian grouping ("Rs 45,000").
// formatMoney is for an amount that must be exact (a payout, an invoice, a cost sheet line, a commission
// split): 1250000 is "Rs 12,50,000". Both round to the rupee. An empty value is an empty cell.
export function formatMoney(value) {
	if (value === "" || value === null || value === undefined) return "";
	const number = Number(value);
	if (Number.isNaN(number)) return "";
	return `Rs ${new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(
		Math.round(number)
	)}`;
}

export function formatBudget(value) {
	if (value === "" || value === null || value === undefined) return "";
	const number = Number(value);
	if (Number.isNaN(number)) return "";
	const trim = (n) => String(Math.round(n * 100) / 100);
	if (number >= 1e7) return `Rs ${trim(number / 1e7)} crore`;
	if (number >= 1e5) return `Rs ${trim(number / 1e5)} lakh`;
	return formatMoney(number);
}

// A short day and time for a table cell that must stay on one line: "24 Nov, 11:44".
export function formatShortWhen(value) {
	const text = formatWhen(value);
	return typeof text === "string" ? text.replace(/ \d{4}/, "") : text;
}
