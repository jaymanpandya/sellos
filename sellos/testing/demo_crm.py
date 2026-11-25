"""The CRM of a demo company: buyer leads on every stage, consent, calls, notes, site visits and follow ups.

The second builder of a company seed (after inventory, before sales and whatsapp). The generators at module level are
pure (no Frappe import, plain dicts, driven only by the `rng` they are given) so a unit test checks the volumes without a
bench. `build(ctx)` turns them into records through the production code: the Client and Lead documents, the consent
functions, the stage move of the pipeline, the telephony call functions and the Lead Activity, Lead Task and Site Visit
documents. It looks every lead up before it makes it, so a second run creates nothing. Seller leads are not made here.
"""

import math
from datetime import datetime, time, timedelta

from sellos.testing import demo_names

STAGES = (
	"New",
	"Consent pending",
	"Contacted",
	"Qualified",
	"Site visit booked",
	"Site visit done",
	"Negotiation",
	"Booking",
	"Closed won",
	"Closed lost",
	"Nurture",
)
STAGE_COUNTS = {
	"New": 24,
	"Consent pending": 12,
	"Contacted": 22,
	"Qualified": 22,
	"Site visit booked": 16,
	"Site visit done": 14,
	"Negotiation": 12,
	"Booking": 10,
	"Closed won": 9,
	"Closed lost": 21,
	"Nurture": 18,
}
# The youngest and oldest a lead on a stage can be, in days: a lead that closed is older than one that is new.
AGE_RANGE = {
	"New": (0, 30),
	"Consent pending": (1, 20),
	"Contacted": (3, 45),
	"Qualified": (5, 60),
	"Site visit booked": (6, 60),
	"Site visit done": (8, 75),
	"Negotiation": (15, 80),
	"Booking": (25, 88),
	"Closed won": (30, 90),
	"Closed lost": (8, 90),
	"Nurture": (10, 90),
}
SOURCE_COUNTS = {
	"Website": 40,
	"Property portal": 36,
	"Referral": 26,
	"Hoarding campaign": 18,
	"Walk in": 18,
	"Instagram": 18,
	"Channel partner": 14,
	"Facebook": 6,
	"Missed call": 4,
}
# Consent kinds: consented (a live record), expired (a lapsed Inquiry), unknown (no record), optedout, dnd.
CONSENT_COUNTS = {"consented": 82, "expired": 20, "unknown": 33, "optedout": 22, "dnd": 23}
STOP_SOURCES = ("Phone call", "WhatsApp", "SMS", "Email", "In person", "Website")
LOST_REASONS = ("Budget too low", "Bought elsewhere", "No longer looking", "Location does not suit", "Other")

LOCALITIES = {
	"bom": (
		"Andheri West",
		"Powai",
		"Bandra East",
		"Worli",
		"Thane",
		"Mulund",
		"Chembur",
		"Goregaon",
		"Borivali",
		"Navi Mumbai",
	),
	"amd": (
		"SG Highway",
		"Prahlad Nagar",
		"Bopal",
		"Shela",
		"Gota",
		"Satellite",
		"Thaltej",
		"Vastrapur",
		"South Bopal",
		"Science City",
	),
}
CITIES = {
	"bom": ("Mumbai", "Mumbai", "Mumbai", "Thane", "Navi Mumbai", "Pune"),
	"amd": ("Ahmedabad", "Ahmedabad", "Ahmedabad", "Gandhinagar", "Vadodara", "Surat"),
}
OVERSEAS = (
	("ae", "Dubai", "United Arab Emirates"),
	("ae", "Abu Dhabi", "United Arab Emirates"),
	("au", "Sydney", "Australia"),
	("au", "Melbourne", "Australia"),
)
# Price of a home by configuration, in lakh, for Mumbai. Ahmedabad is scaled by REGION_SCALE.
CONFIG_LAKH = {
	"1 RK": (30, 50),
	"1 BHK": (55, 95),
	"2 BHK": (110, 220),
	"3 BHK": (240, 450),
	"4 BHK and above": (500, 900),
}
REGION_SCALE = {"bom": 1.0, "amd": 0.45}
PHONE_BASE = {"bom": 41000, "amd": 47000}

# Names of the call outcomes the company seed makes (sellos.crm.call_outcomes.DEFAULT_OUTCOMES).
OUTCOMES = {
	"completed": ("Interested", "Call back later", "Site visit booked", "Not interested"),
	"no-answer": ("Not reachable",),
	"busy": ("Busy",),
	"failed": ("Not reachable",),
}

FOLLOW_UP_TITLES = {
	"New": ("Make the first call", "Introduce yourself and ask what they are looking for"),
	"Consent pending": (
		"Ask for the go ahead to share the brochure",
		"Call to confirm they are happy to be contacted",
	),
	"Contacted": (
		"Send the brochure and the price sheet",
		"Call back about the budget",
		"Share two options on WhatsApp",
	),
	"Qualified": ("Book a site visit", "Send the payment plan", "Call to fix a visit date with the family"),
	"Site visit booked": (
		"Confirm the site visit the day before",
		"Send the location pin and the sales office contact",
	),
	"Site visit done": ("Ask what they thought of the visit", "Send the cost sheet for the unit they liked"),
	"Negotiation": (
		"Take the revised offer to the developer",
		"Call about the final price",
		"Agree the payment schedule",
	),
	"Closed lost": ("Check back in three months",),
	"Nurture": (
		"Share a new launch that fits the budget",
		"Check in about the plan for the year",
		"Send the monthly market note",
	),
}
NOTE_TEXTS = {
	"New": (
		"Came in from {source}. Wants a {config} in {locality}. Not spoken to yet.",
		"Enquiry on {project}. Phone number looks right, email to be asked on the first call.",
	),
	"Consent pending": (
		"Spoke briefly. Asked us to send the details on WhatsApp first. Waiting for the go ahead.",
		"Wants to check with the family before we share prices.",
	),
	"Contacted": (
		"First call done. Looking at a {config} around {locality}, budget up to {budget}.",
		"Sent the brochure of {project}. Will read it over the weekend.",
		"Asked for ready to move options only. Told them about {project}.",
	),
	"Qualified": (
		"Budget of {budget} is firm. Needs the home within the year. Likes {project}.",
		"Spouse is the co decision maker. Both want to see {project} together.",
		"Has a home loan pre approval. Comparing {project} with one more project in {locality}.",
	),
	"Site visit booked": (
		"Visit to {project} fixed. Coming with parents. Asked about parking and the clubhouse.",
		"Wants a weekday visit after office hours. Booked for the evening slot.",
	),
	"Site visit done": (
		"Saw the show flat at {project}. Liked the layout, worried about the price per square foot.",
		"Visited with family. Asked for a revised cost sheet and the payment plan.",
	),
	"Negotiation": (
		"Asking for a better floor and a discount on the parking. Passed to the developer.",
		"Offer of {budget} discussed. Developer will reply by tomorrow.",
		"Wants the booking amount split in two cheques. Checking with accounts.",
	),
	"Booking": (
		"Token received for a unit at {project}. Booking form being filled.",
		"Agreement draft shared with their lawyer.",
	),
	"Closed won": (
		"Booked at {project}. Thank you note sent. Referral asked.",
		"Booking amount received and the allotment letter issued.",
	),
	"Closed lost": (
		"Bought elsewhere. Thanked them and kept the number for later.",
		"Budget did not match what is available in {locality}. Closed.",
		"Stopped answering after the second follow up.",
	),
	"Nurture": (
		"Not ready this year. Check again after the festive season.",
		"Waiting for a bonus and a sale of their old flat. Keep warm.",
		"Prefers to wait for possession dates to firm up at {project}.",
	),
}
CALL_NOTES = {
	"Interested": (
		"Interested. Wants the brochure and a visit this month.",
		"Liked the location, asked for the price list.",
	),
	"Call back later": (
		"In a meeting. Asked to call back in the evening.",
		"Travelling. Asked for a call on Sunday.",
	),
	"Site visit booked": ("Visit fixed for the weekend.", "Fixed a visit with the family."),
	"Not interested": ("Not looking now.", "Has already bought."),
	"Not reachable": ("Phone switched off.", "Rang out twice."),
	"Busy": ("Line busy. Will try again.", "Engaged. Will retry after lunch."),
}
VISIT_NOTES = (
	"Wants a quiet floor away from the road.",
	"Asked for the sample flat key at the sales office.",
	"Coming with the whole family, two cars.",
	"Please send the location pin in the morning.",
)
OUTCOME_NOTES = {
	"Liked it": (
		"Liked the layout and the view. Wants the cost sheet today.",
		"Happy with the amenities. Will decide this week.",
	),
	"Undecided": ("Likes it but is comparing one more project.", "Wants to think about the price."),
	"Wants a second visit": (
		"Wants to come again with the parents.",
		"Wants to see a higher floor next time.",
	),
	"Not interested": ("Too far from the office.", "Did not like the project."),
	"Did not come": ("Did not come and did not pick up.", "Cancelled on the way, asked to reschedule."),
}


# --- Pure generators ---------------------------------------------------------------------------------------


def money_text(amount) -> str:
	"""A budget as a person says it: "85 lakh" or "1.4 crore"."""
	if amount >= 10_000_000:
		return f"{amount / 10_000_000:.2f}".rstrip("0").rstrip(".") + " crore"
	return f"{amount / 100_000:.0f} lakh"


def _round_money(amount) -> int:
	step = 500_000 if amount >= 10_000_000 else 100_000
	return int(round(amount / step) * step)


def _expand(counts) -> list:
	return [key for key, n in counts.items() for _ in range(n)]


def _requirements(rng, region, projects, age_days) -> dict:
	"""What the buyer wants: type, configuration, budget range, timeline and the project or locality they like."""
	kind = rng.choices(
		("Apartment", "Villa", "Plot", "Office", "Shop"),
		weights=(80, 12 if region == "amd" else 5, 6, 3, 3),
	)[0]
	if kind in ("Apartment", "Villa"):
		config = rng.choices(
			("1 RK", "1 BHK", "2 BHK", "3 BHK", "4 BHK and above"), weights=(3, 15, 40, 32, 10)
		)[0]
		if kind == "Villa":
			config = rng.choice(("3 BHK", "4 BHK and above"))
		low_lakh, high_lakh = CONFIG_LAKH[config]
		base = rng.uniform(low_lakh, high_lakh) * 100_000 * REGION_SCALE[region]
		configuration = [config]
		if config in ("2 BHK", "3 BHK") and rng.random() < 0.25:
			configuration.append("3 BHK" if config == "2 BHK" else "2 BHK")
			configuration.sort()
	else:
		base = rng.uniform(40, 150) * 100_000 * REGION_SCALE[region]
		configuration = []
	low = _round_money(base * rng.uniform(0.85, 1.0))
	high = max(_round_money(low * rng.uniform(1.1, 1.35)), low + 100_000)
	if projects and rng.random() < 0.7:
		project = rng.choice(projects)
		project_name, locality = project["name"], project.get("locality") or rng.choice(LOCALITIES[region])
	else:
		project_name, locality = "", rng.choice(LOCALITIES[region])
	localities = [locality]
	if rng.random() < 0.3:
		other = rng.choice(LOCALITIES[region])
		if other != locality:
			localities.append(other)
	timeline = rng.choice(("Immediate", "Within 3 months", "3 to 6 months", "Over 6 months"))
	purpose = rng.choices(("End use", "Investment"), weights=(70, 30))[0]
	return {
		"property_type": kind,
		"configuration": configuration,
		"budget_from": low,
		"budget_to": high,
		"project": project_name,
		"localities": localities,
		"timeline": timeline,
		"purpose": purpose,
		"possession": rng.choice(("Ready", "Under construction", "Any")),
	}


def _path_for(rng, stage) -> list:
	"""The stages a lead went through to reach its stage, first New."""
	i = STAGES.index(stage)
	if stage == "New":
		return ["New"]
	if stage == "Consent pending":
		return ["New", "Consent pending"]
	if stage == "Contacted":
		return ["New", "Consent pending", "Contacted"] if rng.random() < 0.4 else ["New", "Contacted"]
	if stage == "Closed lost":
		route = ["New", "Contacted"]
		if rng.random() < 0.6:
			route.append("Qualified")
		if rng.random() < 0.25:
			route += ["Site visit booked", "Site visit done"]
		return [*route, "Closed lost"]
	if stage == "Nurture":
		route = ["New", "Contacted"]
		if rng.random() < 0.5:
			route.append("Qualified")
		return [*route, "Nurture"]
	return ["New", *STAGES[2 : i + 1]] if i >= 2 else list(STAGES[: i + 1])


def _times_for(rng, path, age, anchors) -> list:
	"""Days after creation of each move on the path (the first is 0), rising, the last before `age`.
	`anchors` fixes some stages; the others are spread between their neighbours."""
	n = len(path)
	times = [0.0] + [anchors.get(stage) for stage in path[1:]]
	end = max(age - 0.1, 0.1)
	if times[-1] is None:
		times[-1] = end if n > 1 else 0.0
	i = 1
	while i < n:
		if times[i] is None:
			j = i
			while times[j] is None:
				j += 1
			start, stop = times[i - 1], times[j]
			for k in range(i, j):
				frac = (k - i + 1) / (j - i + 1)
				times[k] = start + (stop - start) * frac * rng.uniform(0.85, 1.0)
			i = j
		i += 1
	for k in range(1, n):  # strictly rising, never after the end
		times[k] = min(max(times[k], times[k - 1] + 0.02), max(age - 0.02, 0.02 * k))
	return [round(t, 3) for t in times]


def _visit(day, hour, status, confirmation, project, outcome=None, rng=None) -> dict:
	"""A planned site visit: `day` is days ago (negative: in the future)."""
	return {
		"days_ago": day,
		"hour": hour,
		"minute": 30 if hour % 2 else 0,
		"status": status,
		"confirmation": confirmation,
		"outcome": outcome or "",
		"outcome_notes": rng.choice(OUTCOME_NOTES[outcome]) if outcome and rng else "",
		"notes": rng.choice(VISIT_NOTES) if rng and status == "Scheduled" else "",
		"project": project,
	}


def _plan_visits(rng, leads, project_names) -> None:
	"""Give the leads on the visit stages (and a few others) their site visits: past three weeks, next two."""

	def project_of(lead):
		return lead["project"] or rng.choice(project_names)

	def past_day(lead, low=1):
		return rng.randint(low, max(low, min(21, lead["age_days"] - 2)))

	by_stage = {}
	for lead in leads:
		by_stage.setdefault(lead["stage"], []).append(lead)
	booked = by_stage["Site visit booked"]
	for rank, lead in enumerate(booked):
		hour = rng.randint(10, 17)
		if rank < 5:
			visit = _visit(-1, hour, "Scheduled", "Not confirmed", project_of(lead), rng=rng)  # tomorrow
		elif rank < 7:
			visit = _visit(
				0, rng.randint(15, 18), "Scheduled", "Confirmed", project_of(lead), rng=rng
			)  # today
		elif rank < 10:
			visit = _visit(
				-rng.randint(2, 3),
				hour,
				"Scheduled",
				rng.choice(("Confirmed", "Not confirmed")),
				project_of(lead),
				rng=rng,
			)
		elif rank < 13:
			visit = _visit(-rng.randint(4, 13), hour, "Scheduled", "Not confirmed", project_of(lead), rng=rng)
		elif rank == 13:
			visit = _visit(-rng.randint(3, 9), hour, "Scheduled", "Rescheduled", project_of(lead), rng=rng)
		else:
			visit = _visit(-rng.randint(5, 8), hour, "Scheduled", "Confirmed", project_of(lead), rng=rng)
		lead["visits"].append(visit)
		if rank >= 11:  # an earlier visit that was cancelled
			lead["visits"].insert(
				0, _visit(past_day(lead, 2), hour, "Cancelled", "Cancelled", project_of(lead), rng=rng)
			)
	for rank, lead in enumerate(by_stage["Site visit done"]):
		outcome = ("Liked it", "Undecided", "Wants a second visit", "Liked it")[rank % 4]
		lead["visits"].append(
			_visit(past_day(lead), rng.randint(10, 17), "Done", "Confirmed", project_of(lead), outcome, rng)
		)
		if outcome == "Wants a second visit":
			lead["visits"].append(
				_visit(
					-rng.randint(1, 10),
					rng.randint(10, 17),
					"Scheduled",
					"Not confirmed",
					project_of(lead),
					rng=rng,
				)
			)
	for stage in ("Negotiation", "Booking", "Closed won"):
		for rank, lead in enumerate(by_stage[stage]):
			if rank % 3 == 0:
				lead["visits"].append(
					_visit(
						past_day(lead, 12),
						rng.randint(10, 17),
						"Done",
						"Confirmed",
						project_of(lead),
						"Wants a second visit",
						rng,
					)
				)
			lead["visits"].append(
				_visit(
					past_day(lead, 1) if rank % 3 else 3,
					rng.randint(10, 17),
					"Done",
					"Confirmed",
					project_of(lead),
					"Liked it",
					rng,
				)
			)
	older = [lead for lead in by_stage["Closed lost"] if lead["age_days"] >= 10]
	for rank, lead in enumerate(older[:6]):
		outcome = "Did not come" if rank < 3 else "Not interested"
		lead["visits"].append(
			_visit(past_day(lead), rng.randint(10, 17), "Done", "Confirmed", project_of(lead), outcome, rng)
		)
	for rank, lead in enumerate([x for x in by_stage["Nurture"] if x["age_days"] >= 10][:4]):
		if rank < 2:
			lead["visits"].append(
				_visit(
					past_day(lead), rng.randint(10, 17), "Cancelled", "Cancelled", project_of(lead), rng=rng
				)
			)
		else:
			lead["visits"].append(
				_visit(
					past_day(lead),
					rng.randint(10, 17),
					"Done",
					"Confirmed",
					project_of(lead),
					"Did not come",
					rng,
				)
			)
	for lead in [x for x in by_stage["Qualified"] if x["age_days"] >= 10][:3]:
		lead["visits"].append(
			_visit(past_day(lead), rng.randint(10, 17), "Cancelled", "Cancelled", project_of(lead), rng=rng)
		)
	for lead in leads:
		lead["visits"].sort(key=lambda v: -v["days_ago"])


def _anchors(lead) -> dict:
	"""Stage move times that agree with the site visits: booked just before, done just after the visit."""
	done = [v for v in lead["visits"] if v["status"] == "Done"]
	age = lead["age_days"]
	anchors = {}
	if not done:
		return anchors
	first = max(done, key=lambda v: v["days_ago"])  # the earliest visit
	t_visit = max(age - first["days_ago"] + 0.2, 0.5)
	if "Site visit done" in lead["path"]:
		anchors["Site visit done"] = t_visit
		if "Site visit booked" in lead["path"]:
			anchors["Site visit booked"] = max(t_visit - rng_free_gap(lead), 0.2)
	return anchors


def rng_free_gap(lead) -> float:
	"""A fixed, repeatable gap in days between booking a visit and the visit (from the lead's own numbers)."""
	return 1.0 + (lead["index"] % 3)


def _calls_for(rng, lead) -> list:
	"""The calls a lead had: from none on a new lead to three on one that is further on."""
	stage_i = STAGES.index(lead["stage"])
	if lead["overseas_only"]:
		return []
	if stage_i <= 1:
		count = 1 if (lead["stage"] == "New" and rng.random() < 0.3) else 0
	else:
		count = 1 + rng.choice((0, 0, 1))
	calls = []
	for _ in range(count):
		state = rng.choices(("completed", "no-answer", "busy", "failed"), weights=(62, 20, 12, 6))[0]
		outcome = rng.choice(OUTCOMES[state])
		if outcome == "Site visit booked" and stage_i < 4:
			outcome = "Interested"
		if outcome == "Not interested" and lead["stage"] != "Closed lost":
			outcome = "Call back later"
		seconds = rng.randint(35, 540) if state == "completed" else 0
		calls.append(
			{
				"purpose": rng.choices(("Service", "Transactional"), weights=(75, 25))[0],
				"state": state,
				"seconds": seconds,
				"paise": math.ceil(seconds / 60) * rng.randint(55, 90),
				"day": round(rng.uniform(0.05, max(lead["age_days"] - 0.1, 0.1)), 3),
				"outcome": outcome,
				"notes": rng.choice(CALL_NOTES[outcome]),
			}
		)
	calls.sort(key=lambda c: c["day"])
	return calls


def _notes_for(rng, lead) -> list:
	"""Notes, e-mails and meetings logged on the lead, newest last."""
	stage_i = STAGES.index(lead["stage"])
	count = rng.choice((0, 1, 1)) if stage_i == 0 else rng.randint(1, 3) + (1 if stage_i >= 4 else 0)
	texts = NOTE_TEXTS[lead["stage"]]
	items = []
	for _ in range(count):
		kind = rng.choices(("Note", "Email", "Meeting"), weights=(70, 12, 18 if stage_i >= 3 else 0))[0]
		text = rng.choice(texts).format(
			source=lead["source"].lower(),
			config=(lead["configuration"] or ["home"])[0],
			locality=lead["localities"][0],
			budget=money_text(lead["budget_to"]),
			project=lead["project"] or lead["localities"][0],
		)
		items.append(
			{"kind": kind, "text": text, "day": round(rng.uniform(0.05, max(lead["age_days"] - 0.1, 0.1)), 3)}
		)
	items.sort(key=lambda n: n["day"])
	return items


def _follow_up(rng, lead):
	"""The next follow up of an open lead: overdue, today or later. None for a lead that is finished."""
	stage = lead["stage"]
	if stage in ("Booking", "Closed won"):
		return None
	titles = FOLLOW_UP_TITLES.get(stage) or FOLLOW_UP_TITLES["Nurture"]
	kind = rng.choices(("overdue", "today", "later"), weights=(30, 20, 50))[0]
	if kind == "overdue" and lead["age_days"] < 1:
		kind = "today"
	if stage == "Closed lost":
		kind = "later"
	if kind == "overdue":
		offset = -rng.randint(1, min(6, max(int(lead["age_days"]), 1)))
	elif kind == "today":
		offset = 0
	else:
		offset = rng.randint(1, 9 if stage != "Closed lost" else 90)
	return {
		"kind": kind,
		"day_offset": offset,
		"hour": rng.randint(9, 19),
		"minute": rng.choice((0, 15, 30, 45)),
		"title": rng.choice(titles),
	}


def _done_tasks(rng, lead) -> list:
	if lead["age_days"] < 3 or lead["stage"] == "New":
		return []
	titles = (
		"Send the brochure",
		"First call",
		"Share the price sheet",
		"Call back about the budget",
		"Confirm the visit",
	)
	count = rng.choice((0, 1, 1, 2))
	return [
		{"title": rng.choice(titles), "day": round(rng.uniform(0.2, max(lead["age_days"] - 0.5, 0.3)), 3)}
		for _ in range(count)
	]


def generate_leads(rng, region, today, projects, agents, used=None) -> list:
	"""The 180 buyer leads of a company as plain dicts, deterministic from `rng`.

	`projects` are the company's projects ({name, locality, ...}), `agents` the four agent e-mails. Every stage has at
	least 8 leads, every consent state at least 15 and every source of the brief is used. No date is in the future
	except a site visit or a follow up."""
	count = sum(STAGE_COUNTS.values())
	people = demo_names.people(rng, region, count, set() if used is None else used)
	stages = _expand(STAGE_COUNTS)
	rng.shuffle(stages)
	sources = _expand(SOURCE_COUNTS)
	rng.shuffle(sources)
	kinds = _expand(CONSENT_COUNTS)
	rng.shuffle(kinds)
	project_names = [p["name"] for p in projects] or [f"{LOCALITIES[region][0]} Residency"]
	leads = []
	unassigned_left = 8
	for i, person in enumerate(people):
		stage = stages[i]
		low, high = AGE_RANGE[stage]
		age = rng.randint(low, high)
		kind = kinds[i]
		if kind == "expired" and age < 9:
			age = rng.randint(9, max(high, 10))
		nri = person["community"] == "nri"
		purpose_pool = _requirements(rng, region, projects, age)
		overseas = rng.choice(OVERSEAS) if nri else None
		first, last = person["first"].lower(), person["last"].lower()
		email = f"{first}.{last}{rng.randint(1, 99)}@example.com"
		leads.append(
			{
				"index": i,
				"name": person["name"],
				"community": person["community"],
				"stage": stage,
				"source": sources[i],
				"agent": None,
				"age_days": age,
				"created_hour": rng.randint(9, 20),
				"created_minute": rng.randint(0, 59),
				"consent": kind,
				"client_type": "NRI"
				if nri
				else ("Investor" if purpose_pool["purpose"] == "Investment" else "Buyer"),
				"phone_seed": PHONE_BASE[region] + i,
				"overseas": overseas,
				"overseas_only": bool(nri and rng.random() < 0.4),
				"email": email,
				"city": overseas[1] if overseas else rng.choice(CITIES[region]),
				**purpose_pool,
				"lost_reason": rng.choice(LOST_REASONS) if stage == "Closed lost" else "",
				"visits": [],
			}
		)
	# At least eight NRI clients on a company whose community mix draws few of them.
	nri_count = sum(1 for lead in leads if lead["client_type"] == "NRI")
	for lead in leads:
		if nri_count >= 8:
			break
		if lead["client_type"] != "NRI" and lead["stage"] in ("Contacted", "Qualified", "Nurture"):
			lead.update(client_type="NRI", overseas=rng.choice(OVERSEAS), overseas_only=False)
			lead["city"] = lead["overseas"][1]
			nri_count += 1
	for lead in leads:
		if lead["stage"] == "New" and unassigned_left > 0:
			unassigned_left -= 1
		else:
			lead["agent"] = agents[lead["index"] % len(agents)] if agents else None
	for lead in leads[: len(leads) // 2]:  # shuffle which agent gets which lead, deterministically
		if lead["agent"] and rng.random() < 0.3:
			lead["agent"] = rng.choice(agents)
	# A duplicate pair (the same phone) and leads with no e-mail, so the empty state reads "Not filled in".
	if len(leads) > 41:
		leads[41]["phone_seed"] = leads[40]["phone_seed"]
		leads[41]["overseas"], leads[41]["overseas_only"] = None, False
		if leads[41]["client_type"] == "NRI":
			leads[41]["client_type"] = "Buyer"
	for position in (7, 23, 58, 97, 133):
		leads[position]["email"] = None
	_plan_visits(rng, leads, project_names)
	for lead in leads:
		lead["path"] = _path_for(rng, lead["stage"])
		times = _times_for(rng, lead["path"], lead["age_days"], _anchors(lead))
		lead["moves"] = [{"stage": s, "day": t} for s, t in zip(lead["path"], times, strict=True)]
		lead["calls"] = _calls_for(rng, lead)
		lead["notes_log"] = _notes_for(rng, lead)
		lead["follow_up"] = _follow_up(rng, lead)
		lead["done_tasks"] = _done_tasks(rng, lead)
		lead["notes"] = _lead_note(rng, lead)
	return leads


def _lead_note(rng, lead) -> str:
	where = lead["project"] or ", ".join(lead["localities"])
	return rng.choice(
		(
			f"Interested in {where}. Looking for a {', '.join(lead['configuration']) or lead['property_type'].lower()} "
			f"up to {money_text(lead['budget_to'])}.",
			f"Enquired about {where} through {lead['source'].lower()}. Budget {money_text(lead['budget_from'])} "
			f"to {money_text(lead['budget_to'])}.",
			f"Wants {where}. Timeline: {lead['timeline'].lower()}.",
		)
	)


def count_activities(leads) -> int:
	"""Lead Activity rows the leads make: every call, note, e-mail and meeting, and one meeting per visit that took
	place."""
	total = 0
	for lead in leads:
		total += len(lead["calls"]) + len(lead["notes_log"])
		total += sum(1 for v in lead["visits"] if v["status"] == "Done")
	return total


# --- The Frappe side ---------------------------------------------------------------------------------------


def build(ctx):
	"""Make the company's buyer leads and everything on them. A lead that exists is left as it is."""
	import frappe
	from frappe.utils import now_datetime

	from sellos.crm import consent, pipeline
	from sellos.telephony import call_log
	from sellos.telephony.base import CallEvent, ProviderError
	from sellos.tests import phones

	now = now_datetime()
	agents = list(ctx.users["agents"])
	region = ctx.word
	pipeline.ensure_default_stages()
	_ensure_sources(ctx)
	specs = generate_leads(ctx.rng, region, ctx.today, ctx.projects, agents, ctx.used_names)
	call_total = skipped_calls = 0

	def when_of(created, days):
		return min(created + timedelta(days=days), now - timedelta(minutes=1))

	def stamp(doctype, name, when):
		frappe.db.set_value(doctype, name, {"creation": when, "modified": when}, update_modified=False)

	for spec in specs:
		age = spec["age_days"]
		created = datetime.combine(
			ctx.today - timedelta(days=age), time(spec["created_hour"], spec["created_minute"])
		)
		created = min(created, now - timedelta(minutes=90))
		client = _client(ctx, spec, phones)
		existing = frappe.db.get_value("Lead", {"client": client, "pipeline": "Buyer"}, "name")
		if existing:
			ctx.leads.append(_summary(frappe, existing, spec, client))
			continue
		values = {
			"doctype": "Lead",
			"client": client,
			"source": spec["source"],
			"assigned_to": spec["agent"],
			"notes": spec["notes"],
			"budget_from": spec["budget_from"],
			"budget_to": spec["budget_to"],
			"configuration": "\n".join(spec["configuration"]),
			"property_type": spec["property_type"],
			"preferred_localities": "\n".join(spec["localities"]),
			"purpose": spec["purpose"],
			"timeline": spec["timeline"],
			"possession": spec["possession"],
		}
		doc = frappe.get_doc(values)
		doc.flags.ignore_permissions = True
		doc.insert()
		lead = doc.name
		ctx.count("created", "Lead")
		if not spec["agent"]:
			frappe.db.set_value("Lead", lead, "assigned_to", None, update_modified=False)
		owner = spec["agent"] or ctx.users.get("admin")
		if owner:
			frappe.db.set_value("Lead", lead, "owner", owner, update_modified=False)
		actor = spec["agent"] or ctx.users.get("admin") or frappe.session.user
		touched = [created]

		# The first row of the stage log, as the first stage of the pipeline would write it.
		doc = frappe.get_doc("Lead", lead)
		doc.append(
			"stage_log",
			{
				"changed_on": created,
				"changed_by": actor,
				"from_stage": "",
				"to_stage": spec["moves"][0]["stage"],
				"lost_reason": "",
				"warning": "",
			},
		)
		doc.flags.ignore_permissions = True
		doc.save()

		_consent(frappe, consent, ctx, lead, spec, created, when_of)

		for move in spec["moves"][1:]:
			reason = spec["lost_reason"] if move["stage"] == "Closed lost" else None
			pipeline.move_lead(lead, move["stage"], lost_reason=reason)
		rows = frappe.get_all(
			"Lead Stage Change",
			filters={"parent": lead, "parenttype": "Lead"},
			fields=["name"],
			order_by="idx asc",
		)
		for row, move in zip(rows, spec["moves"], strict=False):
			at = when_of(created, move["day"])
			frappe.db.set_value(
				"Lead Stage Change", row.name, {"changed_on": at, "changed_by": actor}, update_modified=False
			)
			touched.append(at)
		ctx.count("created", "Lead Stage Change", len(rows))

		for call in spec["calls"]:
			at = when_of(created, call["day"])
			touched.append(at)
			made = _call(
				frappe,
				call_log,
				CallEvent,
				ProviderError,
				lead,
				call,
				at,
				spec["agent"] or agents[spec["index"] % 4],
			)
			if made:
				call_total += 1
				ctx.count("created", "Call Log")
			else:
				skipped_calls += 1
			_activity(ctx, lead, "Call", at, call["notes"], call["outcome"], call["seconds"], stamp)
		for note in spec["notes_log"]:
			at = when_of(created, note["day"])
			touched.append(at)
			_activity(ctx, lead, note["kind"], at, note["text"], None, 0, stamp)
		for visit in spec["visits"]:
			touched.append(_visit_doc(frappe, ctx, lead, spec, visit, now, stamp))
		_tasks(frappe, ctx, lead, spec, created, now, when_of, stamp)

		last = max(touched)
		frappe.db.set_value(
			"Lead", lead, {"creation": created, "modified": min(last, now)}, update_modified=False
		)
		ctx.leads.append(_summary(frappe, lead, spec, client))
	if skipped_calls:
		print(f"demo crm: {skipped_calls} calls skipped (no Indian route for the number)")


def _ensure_sources(ctx):
	import frappe

	for name in SOURCE_COUNTS:
		if not frappe.db.exists("Lead Source", name):
			frappe.get_doc({"doctype": "Lead Source", "source_name": name, "enabled": 1}).insert(
				ignore_permissions=True
			)
			ctx.count("created", "Lead Source")


def _client(ctx, spec, phones):
	import frappe

	existing = frappe.db.get_value("Client", {"client_name": spec["name"]}, "name")
	if existing:
		return existing
	overseas = spec["overseas"]
	phone, overseas_phone = "", ""
	if overseas:
		maker = phones.ae_mobile if overseas[0] == "ae" else phones.au_mobile
		overseas_phone = maker(spec["phone_seed"] + 3000)
	if not (overseas and spec["overseas_only"]):
		phone = phones.in_mobile(spec["phone_seed"])
	doc = frappe.get_doc(
		{
			"doctype": "Client",
			"client_name": spec["name"],
			"client_type": spec["client_type"],
			"phone": phone,
			"overseas_phone": overseas_phone,
			"email": spec["email"] or "",
			"city": spec["city"],
			"country_of_residence": overseas[2] if overseas else None,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	ctx.count("created", "Client")
	return doc.name


def _summary(frappe, lead, spec, client) -> dict:
	row = frappe.db.get_value(
		"Lead",
		lead,
		["stage", "assigned_to", "source", "creation", "consent_status", "budget_to", "configuration"],
		as_dict=True,
	)
	phone = frappe.db.get_value("Client", client, "phone") or frappe.db.get_value(
		"Client", client, "overseas_phone"
	)
	return {
		"name": lead,
		"client": client,
		"client_name": spec["name"],
		"stage": row.stage,
		"agent": row.assigned_to,
		"source": row.source,
		"created_on": row.creation,
		"consent": row.consent_status,
		"phone": phone,
		"budget_to": row.budget_to,
		"configuration": row.configuration,
	}


def _consent(frappe, consent, ctx, lead, spec, created, when_of):
	kind = spec["consent"]
	age = spec["age_days"]
	if kind in ("consented", "expired") or (kind == "optedout" and spec["index"] % 2 == 0):
		if kind == "expired":
			basis = "Inquiry"
		elif kind == "consented" and age <= 5 and spec["index"] % 2 == 0:
			basis = "Inquiry"
		elif kind == "consented" and age <= 80 and spec["index"] % 4 == 1:
			basis = "Application"
		else:
			basis = "Consent"
		frappe.get_doc(
			{
				"doctype": "Consent Record",
				"lead": lead,
				"basis": basis,
				"recorded_on": when_of(created, 0.04),
				"evidence_link": f"https://example.com/consent/{lead.lower()}",
			}
		).insert(ignore_permissions=True)
		ctx.count("created", "Consent Record")
	if kind == "optedout":
		source = STOP_SOURCES[spec["index"] % len(STOP_SOURCES)]
		consent.record_opt_out(lead, source, on=when_of(created, max(age * 0.6, 0.1)))
	elif kind == "dnd":
		consent.record_dnd_result(lead, 1, on=when_of(created, max(age * 0.2, 0.05)))
	consent.sync_lead_status(lead)


def _call(frappe, call_log, CallEvent, ProviderError, lead, call, at, agent) -> bool:
	try:
		placed = call_log.place_logged_call(lead, call["purpose"])
	except ProviderError:
		return False  # an overseas number has no Indian route: that lead has no call
	log = placed["log"]
	if not log:
		return False
	call_id = frappe.db.get_value("Call Log", log, "call_id")
	call_log.apply_event(
		CallEvent(call_id, call["state"], duration=call["seconds"]), cost=call["paise"], cost_unit="paise"
	)
	frappe.db.set_value(
		"Call Log",
		log,
		{"started_on": at, "agent": agent, "outcome": call["outcome"], "creation": at, "modified": at},
		update_modified=False,
	)
	return True


def _activity(ctx, lead, kind, at, text, outcome, seconds, stamp):
	import frappe

	doc = frappe.get_doc(
		{
			"doctype": "Lead Activity",
			"lead": lead,
			"activity_type": kind,
			"activity_date": at,
			"outcome": outcome,
			"duration_seconds": seconds,
			"notes": text,
		}
	).insert(ignore_permissions=True)
	stamp("Lead Activity", doc.name, at)
	ctx.count("created", "Lead Activity")


def _visit_doc(frappe, ctx, lead, spec, visit, now, stamp):
	day = ctx.today - timedelta(days=visit["days_ago"])
	at = datetime.combine(day, time(visit["hour"], visit["minute"]))
	if visit["status"] == "Done":
		at = min(at, now - timedelta(hours=3))
	doc = frappe.get_doc(
		{
			"doctype": "Site Visit",
			"lead": lead,
			"project_name": visit["project"],
			"visit_datetime": at,
			"status": visit["status"],
			"agent": spec["agent"],
			"notes": visit["notes"],
			"confirmation_status": visit["confirmation"],
			"visit_outcome": visit["outcome"] or None,
			"outcome_notes": visit["outcome_notes"],
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	ctx.count("created", "Site Visit")
	booked_on = min(at - timedelta(days=2), now - timedelta(minutes=5))
	stamp("Site Visit", doc.name, booked_on)
	if visit["confirmation"] in ("Confirmed", "Rescheduled"):
		frappe.db.set_value(
			"Site Visit", doc.name, "confirmed_on", min(at - timedelta(hours=20), now), update_modified=False
		)
	if visit["status"] == "Done":
		_activity(
			ctx,
			lead,
			"Meeting",
			at + timedelta(hours=2),
			f"Site visit at {visit['project']}: {visit['outcome_notes']}",
			None,
			0,
			stamp,
		)
		return at + timedelta(hours=2)
	return min(booked_on, now)


def _tasks(frappe, ctx, lead, spec, created, now, when_of, stamp):
	agent = spec["agent"]
	for done in spec["done_tasks"]:
		at = when_of(created, done["day"])
		doc = frappe.get_doc(
			{
				"doctype": "Lead Task",
				"lead": lead,
				"title": done["title"],
				"due_at": at,
				"status": "Done",
				"assigned_to": agent,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
		frappe.db.set_value(
			"Lead Task", doc.name, "completed_on", at + timedelta(minutes=20), update_modified=False
		)
		stamp("Lead Task", doc.name, max(created, at - timedelta(days=1)))
		ctx.count("created", "Lead Task")
	follow = spec["follow_up"]
	if not follow:
		return
	due = datetime.combine(
		ctx.today + timedelta(days=follow["day_offset"]), time(follow["hour"], follow["minute"])
	)
	doc = frappe.get_doc(
		{
			"doctype": "Lead Task",
			"lead": lead,
			"title": follow["title"],
			"due_at": due,
			"status": "Open",
			"assigned_to": agent,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	stamp("Lead Task", doc.name, min(max(created, due - timedelta(days=2)), now - timedelta(minutes=1)))
	ctx.count("created", "Lead Task")
