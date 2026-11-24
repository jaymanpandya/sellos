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

// Rupees with Indian digit grouping: 1250000 is "Rs 12,50,000". An empty value is an empty cell.
// A second argument gives the decimals to keep (a payout shows paise: formatMoney(3200000, 2)).
export function formatMoney(value, decimals = 0) {
	if (value === "" || value === null || value === undefined) return "";
	const number = Number(value);
	if (Number.isNaN(number)) return "";
	return `Rs ${new Intl.NumberFormat("en-IN", {
		minimumFractionDigits: decimals,
		maximumFractionDigits: decimals,
	}).format(number)}`;
}
