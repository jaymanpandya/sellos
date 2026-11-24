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
