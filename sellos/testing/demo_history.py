"""Make the seeded history agree with itself (SOS-LOOP).

The builders of the demo make a lead's stage log backdated, but the records they make through the production
methods (a consent record, an approved deal, an approved payout, the stage move a booking makes) carry the time
of the seed run. A lead then shows a deal approved after the lead's own last activity, consent given weeks after
the first call, or a booking in its stage log that is "now" while its deal is months old.

`align` runs after every builder and restamps those records, earliest first and never later than the next event
of the same lead or deal, and never in the future. The planning is in pure functions (`chain`, `plan_consent`,
`plan_deal`) so the rules are tested without a database (test_demo_history.py); `align` only reads the records and
writes the planned times. It changes no value but a time, and it is safe to run again: a second run plans the
times it already holds.
"""

from datetime import datetime, time, timedelta

MINUTE = timedelta(minutes=1)


def chain(times, floor, ceiling):
	"""The times, kept in their given order, never earlier than `floor`, each at least a minute after the one
	before, and none later than `ceiling` (when the room runs out they share the ceiling)."""
	out = []
	previous = floor - MINUTE
	for when in times:
		when = max(when, previous + MINUTE)
		when = min(when, ceiling)
		out.append(when)
		previous = when
	return out


def plan_consent(created, first_event, records, opted_out_on, now):
	"""New times for a lead's consent records and its opt out.

	`records` are the `recorded_on` times, oldest first. Consent is recorded before the lead's next event (its
	first call, note or stage move after creation) and never before the lead exists, each record after the one
	before. An opt out comes after the consent it ends and never in the future. Returns (records, opted_out_on)."""
	ceiling = now - MINUTE
	latest = max(created, (first_event - MINUTE) if first_event else created)
	capped = [min(r, latest) for r in records]
	planned = chain(capped, created, ceiling)
	stop = opted_out_on
	if stop is not None:
		floor = (planned[-1] if planned else created) + MINUTE
		stop = min(max(stop, floor), ceiling)
	return planned, stop


def plan_deal(deal_date, previous_event, approved, now, payouts):
	"""New times for a deal and its payouts.

	The deal is made at 10:00 on its date, or an hour after the lead's last earlier event when that is later. It is
	approved four hours after it is made. A payout is made when the deal is approved and approved a day later
	(when it ever was); a payout paid on a date is paid on or after the day it was approved. Nothing after `now`.
	`payouts` is a list of (approved_flag, paid_on) tuples. Returns (made, approved_on, [(made, approved_on, paid_on)])."""
	ceiling = now - MINUTE
	made = datetime.combine(deal_date, time(10, 0))
	if previous_event is not None:
		made = max(made, previous_event + timedelta(hours=1))
	made = min(made, ceiling)
	approved_on = min(made + timedelta(hours=4), ceiling) if approved else None
	base = approved_on or made
	planned = []
	for payout_approved, paid_on in payouts:
		p_made = min(base, ceiling)
		p_approved = min(p_made + timedelta(days=1), ceiling) if payout_approved else None
		if paid_on is not None and p_approved is not None and paid_on < p_approved.date():
			paid_on = p_approved.date()
		if paid_on is not None and paid_on > ceiling.date():
			paid_on = ceiling.date()
		planned.append((p_made, p_approved, paid_on))
	return made, approved_on, planned


# -- the database side ------------------------------------------------------------------------------------


def align(ctx=None):
	"""Restamp the consent records, stage log, last activity, deals and payouts of the site. Returns counts."""
	import frappe
	from frappe.utils import get_datetime, now_datetime

	now = now_datetime()
	counts = {"leads": 0, "consent_records": 0, "deals": 0, "payouts": 0}
	deal_of_lead = _deals_by_lead(frappe)
	for lead in frappe.get_all("Lead", fields=["name", "creation", "opted_out_on"]):
		created = get_datetime(lead.creation)
		stage_rows = frappe.get_all(
			"Lead Stage Change",
			filters={"parent": lead.name, "parenttype": "Lead"},
			fields=["name", "changed_on"],
			order_by="idx asc",
		)
		stage_times = [get_datetime(r.changed_on) for r in stage_rows]
		deal = deal_of_lead.get(lead.name)
		if deal and stage_rows:
			stage_times = _stage_with_deal(stage_times, deal, now)
		stage_times = chain(stage_times, created, now - MINUTE) if stage_times else []
		for row, when in zip(stage_rows, stage_times, strict=False):
			frappe.db.set_value("Lead Stage Change", row.name, "changed_on", when, update_modified=False)

		events = list(stage_times[1:]) + _worked_times(frappe, lead.name)
		first_event = min(events) if events else None
		records = frappe.get_all(
			"Consent Record",
			filters={"lead": lead.name},
			fields=["name", "recorded_on", "expires_on"],
			order_by="recorded_on asc, creation asc",
		)
		planned, stop = plan_consent(
			created,
			first_event,
			[get_datetime(r.recorded_on) for r in records],
			get_datetime(lead.opted_out_on) if lead.opted_out_on else None,
			now,
		)
		for record, when in zip(records, planned, strict=False):
			old = get_datetime(record.recorded_on)
			values = {"recorded_on": when, "creation": when, "modified": when}
			if record.expires_on:
				values["expires_on"] = get_datetime(record.expires_on) + (when - old)
			frappe.db.set_value("Consent Record", record.name, values, update_modified=False)
			counts["consent_records"] += 1
		if stop is not None:
			frappe.db.set_value("Lead", lead.name, "opted_out_on", stop, update_modified=False)

		last = max([created, *stage_times, *planned, *([stop] if stop else []), *events])
		frappe.db.set_value("Lead", lead.name, "modified", min(last, now), update_modified=False)
		counts["leads"] += 1

	counts["deals"], counts["payouts"] = _align_deals(frappe, now)
	return counts


def _worked_times(frappe, lead):
	from frappe.utils import get_datetime

	times = [
		get_datetime(t) for t in frappe.get_all("Lead Activity", filters={"lead": lead}, pluck="creation")
	]
	times += [
		get_datetime(t) for t in frappe.get_all("Call Log", filters={"lead": lead}, pluck="started_on") if t
	]
	return times


def _deals_by_lead(frappe):
	out = {}
	for d in frappe.get_all(
		"Deal",
		filters={"lead": ["is", "set"], "archived": 0},
		fields=["name", "lead", "deal_date"],
		order_by="deal_date asc",
	):
		out.setdefault(d.lead, d)
	return out


def _stage_with_deal(stage_times, deal, now):
	"""The stage moves a booking made at the time of the seed run belong at the deal's time: the rows stamped in
	the last two hours are moved to the deal's day (they are then chained after the lead's earlier rows)."""
	from frappe.utils import getdate

	recent = now - timedelta(hours=2)
	at = datetime.combine(getdate(deal.deal_date), time(10, 5))
	return [at if t >= recent else t for t in stage_times]


def _align_deals(frappe, now):
	from frappe.utils import get_datetime, getdate

	deals = payouts = 0
	for deal in frappe.get_all(
		"Deal", fields=["name", "lead", "deal_date", "approved_on", "cancelled_on"], filters={"archived": 0}
	):
		if not deal.deal_date:
			continue
		previous = None
		if deal.lead:
			rows = frappe.get_all(
				"Lead Stage Change",
				filters={"parent": deal.lead, "parenttype": "Lead"},
				fields=["changed_on"],
				order_by="idx asc",
			)
			day = datetime.combine(getdate(deal.deal_date), time(0, 0))
			earlier = [get_datetime(r.changed_on) for r in rows if get_datetime(r.changed_on) < day]
			previous = max(earlier) if earlier else None
		rows = frappe.get_all(
			"Commission Payout",
			filters={"deal": deal.name},
			fields=["name", "approved_on", "paid_on"],
			order_by="creation asc",
		)
		made, approved_on, planned = plan_deal(
			getdate(deal.deal_date),
			previous,
			bool(deal.approved_on),
			now,
			[(bool(r.approved_on), getdate(r.paid_on) if r.paid_on else None) for r in rows],
		)
		values = {"creation": made, "modified": made}
		if approved_on:
			values["approved_on"] = approved_on
		if deal.cancelled_on:
			values["cancelled_on"] = min(made + timedelta(days=2), now - MINUTE)
		frappe.db.set_value("Deal", deal.name, values, update_modified=False)
		deals += 1
		for row, (p_made, p_approved, paid_on) in zip(rows, planned, strict=False):
			values = {"creation": p_made, "modified": p_made}
			if p_approved:
				values["approved_on"] = p_approved
			if paid_on:
				values["paid_on"] = paid_on
			frappe.db.set_value("Commission Payout", row.name, values, update_modified=False)
			payouts += 1
	return deals, payouts
