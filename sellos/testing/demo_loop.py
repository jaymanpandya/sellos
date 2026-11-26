"""The demo's content for the Leads and Sales round (SOS-LOOP): the company profile with a logo and colours of
its own for each company, notes of every type with images on sellers and mandates, mandates that are signed and
mandates that wait for a signature (their DocuSeal state is seeded as if DocuSeal had answered: no real submission
exists), the Dossier PDF of signed mandates, and deals with one, two and three channel partner splits in every
period (day, week, month and year to date, and outside the year).

Pure functions plan the content so it is tested without a bench (test_demo_loop.py); `build` writes it through the
production methods as the people who would, then backdates what carries the time of the run. A second run finds
what is there and creates nothing.
"""

import io
from datetime import date, timedelta

PROFILES = {
	"bom": {
		"brand_color": "#0B5D3B",
		"accent_color": "#B45309",
		"rera_number": "A51700045621",
		"address": "402 Linking Road, Bandra West",
		"contact_phone": "+91 22 4000 4455",
		"website": "https://bom.demo.example.com",
		"footer_text": "Pandya Realtors - BOM | MahaRERA registered | Confidential",
		"logo": {"shape": "square", "letters": "PB", "fill": (11, 93, 59), "ink": (255, 255, 255)},
		"signer": "Nikhil Pandya",
	},
	"amd": {
		"brand_color": "#7A1F3D",
		"accent_color": "#1F6F8B",
		"rera_number": "PR/GJ/AHMEDABAD/RAA09876/121120",
		"address": "11 Law Garden Road, Ellisbridge",
		"contact_phone": "+91 79 4000 6677",
		"website": "https://amd.demo.example.com",
		"footer_text": "Pandya Realtors - AMD | GujRERA registered | Confidential",
		"logo": {"shape": "circle", "letters": "PA", "fill": (122, 31, 61), "ink": (255, 255, 255)},
		"signer": "Hetal Pandya",
	},
}

# One note of every type, with what a person would write. `photos` is how many pictures it carries.
NOTE_PLAN = (
	("Call", "Spoke to the owner for ten minutes. They are in no hurry but want a serious buyer.", 0, 3),
	(
		"Site visit",
		"Visited with the owner. Flat is in good order, society is quiet, parking is covered.",
		0,
		7,
	),
	(
		"Owner requirement",
		"Wants a clean deal, no brokerage from the buyer, and possession after Diwali.",
		0,
		12,
	),
	("Price discussion", "Owner asked for 1.25 crore. Our comparison supports 1.15 to 1.2 crore.", 0, 18),
	("Legal and title", "Title deed and society NOC seen. Index II copy requested from the owner.", 0, 24),
	("Inspection", "Seepage mark on the living room wall, otherwise fine. Photos taken.", 2, 30),
	("Photos", "Hall, bedroom and balcony, taken on the day of the visit.", 3, 36),
	("Document", "Society NOC and the latest maintenance receipt, scanned.", 0, 42),
	("Follow up", "Call back on Thursday with two buyer shortlists.", 0, 2),
	("Other", "The owner's brother lives in the flat above and may want first refusal.", 0, 5),
)
OTHER_LABEL = "Family"
NOTE_SELLERS = 8  # sellers that carry notes
PDF_MANDATES = 3  # signed mandates that carry a Dossier PDF

# (partners, agent, partner shares, company) for a deal with one, two and three channel partner splits.
SPLITS = {
	1: (50, (20,), 30),
	2: (40, (15, 15), 30),
	3: (35, (10, 10, 10), 35),
}
PROPERTY_PREFIX = "Demo Split Flat"


def deal_dates(today: date) -> list[date]:
	"""A date in each period that ends today, one outside the year, and none in the future: today, the Monday of
	this week, the 1st of the month, 15 January (or the 1st of January) and 20 December last year."""
	week = today - timedelta(days=today.weekday())
	month = today.replace(day=1)
	year = (
		today.replace(month=1, day=15)
		if today.replace(month=1, day=15) < month
		else today.replace(month=1, day=1)
	)
	last_year = date(today.year - 1, 12, 20)
	return sorted({today, week, month, year, last_year})


def deal_plan(today: date) -> list[dict]:
	"""The extra deals: every date gets a deal, today gets one of each (1, 2 and 3 partner splits), and the partner
	count of the others cycles. Each row is {date, partners, agent, shares, company, price, ordinal}."""
	rows = []
	cycle = (2, 3, 1)
	for index, when in enumerate(deal_dates(today)):
		counts = (1, 2, 3) if when == today else (cycle[index % 3],)
		for count in counts:
			agent, shares, company = SPLITS[count]
			rows.append(
				{
					"date": when,
					"partners": count,
					"agent": agent,
					"shares": shares,
					"company": company,
					"price": 11_500_000 + 750_000 * (len(rows) % 5),
					"ordinal": len(rows) + 1,
				}
			)
	return rows


def logo_png(spec: dict, size=240) -> bytes:
	"""A simple monogram logo: a coloured square or circle with two letters. Different for each company."""
	from PIL import Image, ImageDraw, ImageFont

	image = Image.new("RGBA", (size, size), (255, 255, 255, 0))
	draw = ImageDraw.Draw(image)
	if spec["shape"] == "circle":
		draw.ellipse((6, 6, size - 6, size - 6), fill=spec["fill"])
	else:
		draw.rounded_rectangle((6, 6, size - 6, size - 6), radius=28, fill=spec["fill"])
	try:
		font = ImageFont.load_default(size=size // 2)
	except TypeError:  # an older Pillow has one fixed size
		font = ImageFont.load_default()
	draw.text((size / 2, size / 2), spec["letters"], fill=spec["ink"], font=font, anchor="mm")
	out = io.BytesIO()
	image.save(out, "PNG")
	return out.getvalue()


def photo_png(seed: int, size=(480, 320)) -> bytes:
	"""A small picture of a room's colours, different for each seed, for the notes' photos."""
	from PIL import Image, ImageDraw

	tones = (
		(214, 196, 170),
		(170, 188, 176),
		(188, 176, 200),
		(226, 208, 150),
		(150, 176, 204),
		(206, 160, 150),
	)
	wall, floor = tones[seed % len(tones)], tones[(seed + 2) % len(tones)]
	image = Image.new("RGB", size, wall)
	draw = ImageDraw.Draw(image)
	draw.rectangle((0, int(size[1] * 0.66), size[0], size[1]), fill=floor)
	draw.rectangle((size[0] * 0.58, size[1] * 0.12, size[0] * 0.88, size[1] * 0.58), fill=(236, 244, 250))
	draw.rectangle(
		(size[0] * 0.1, size[1] * 0.45, size[0] * 0.36, size[1] * 0.7), fill=tones[(seed + 4) % len(tones)]
	)
	out = io.BytesIO()
	image.save(out, "PNG")
	return out.getvalue()


# --- the Frappe side ----------------------------------------------------------------------------------------


def _as(email):
	from sellos.tests import ui_fixtures

	return ui_fixtures._as_user(email)


def build(ctx):
	"""Make the profile, the notes, the signing states, the Dossier PDFs and the split deals of one company."""
	admin = ctx.users["admin"]
	with _as(admin):
		_profile(ctx)
	_notes(ctx)
	_signing(ctx)
	_dossier_pdfs(ctx)
	with _as(admin):
		_split_deals(ctx)


def _profile(ctx):
	import base64

	import frappe

	from sellos.inventory import branding

	spec = PROFILES[ctx.word]
	if frappe.db.get_single_value("SellOS Settings", "brand_color") == spec[
		"brand_color"
	] and frappe.db.get_single_value("SellOS Settings", "logo"):
		return
	values = {k: v for k, v in spec.items() if k not in ("logo", "signer")}
	branding.save_company_profile({**values, "company_name": ctx.company_name})
	branding.upload_company_logo(f"logo-{ctx.word}.png", base64.b64encode(logo_png(spec["logo"])).decode())
	frappe.db.set_single_value("SellOS Settings", "docuseal_signer_name", spec["signer"])
	frappe.db.set_single_value(
		"SellOS Settings", "docuseal_signer_email", f"signer@{ctx.word}.demo.example.com"
	)
	ctx.count("created", "Company profile")


def _backdate(name, days_ago, ctx, hour=11):
	import frappe
	from frappe.utils import get_datetime

	when = get_datetime(f"{ctx.today - timedelta(days=days_ago)} {hour:02d}:15:00")
	frappe.db.set_value("Record Note", name, {"creation": when, "modified": when}, update_modified=False)


def _notes(ctx):
	"""Notes of every type on the first sellers (and on their signed mandates), written as the seller's agent."""
	import base64

	import frappe

	from sellos.crm import notes
	from sellos.tests.files import tiny_pdf

	types = None
	made = 0
	for position, seller in enumerate(ctx.sellers[:NOTE_SELLERS]):
		if frappe.db.exists("Record Note", {"lead": seller["name"]}):
			continue
		mandate = next(
			(m for m in ctx.mandates if m["lead"] == seller["name"] and m["status"] == "Signed"), None
		)
		with _as(seller["agent"]):
			types = types or {t["label"]: t["name"] for t in notes.note_types()["types"]}
			# Eight sellers: each carries four or five notes, the types rotating so every type appears.
			for step in range(5):
				label, text, photos, days = NOTE_PLAN[(position * 3 + step * 2) % len(NOTE_PLAN)]
				files = [
					{
						"filename": f"{label.lower().replace(' ', '-')}-{n + 1}.png",
						"content_base64": base64.b64encode(photo_png(position + n + step)).decode(),
					}
					for n in range(photos)
				]
				if label == "Document":
					files.append(
						{
							"filename": "society-noc.pdf",
							"content_base64": base64.b64encode(tiny_pdf()).decode(),
						}
					)
				result = notes.add_note(
					types[label],
					text,
					lead=seller["name"],
					mandate=mandate["name"]
					if mandate and label in ("Legal and title", "Inspection", "Photos")
					else None,
					custom_label=OTHER_LABEL if label == "Other" else "",
					files=files,
				)
				_backdate(result["name"], days + position, ctx, 10 + step)
				made += 1
	if made:
		ctx.count("created", "Record Note", made)
	_cover_every_type(ctx, types)


def _cover_every_type(ctx, types):
	"""The rotation above can leave a type out: put any missing type on the first seller."""
	import frappe

	from sellos.crm import notes

	if not ctx.sellers:
		return
	seller = ctx.sellers[0]
	have = {
		frappe.db.get_value("Note Type", n["note_type"], "label")
		for n in frappe.get_all("Record Note", filters={"removed": 0}, fields=["note_type"])
	}
	types = types or {}
	with _as(seller["agent"]):
		types = types or {t["label"]: t["name"] for t in notes.note_types()["types"]}
		for label, text, _photos, days in NOTE_PLAN:
			if label in have:
				continue
			result = notes.add_note(
				types[label], text, lead=seller["name"], custom_label=OTHER_LABEL if label == "Other" else ""
			)
			_backdate(result["name"], days, ctx)
			ctx.count("created", "Record Note")


def _signing(ctx):
	"""A DocuSeal state on mandates: two signed through DocuSeal, one waiting for the seller (Sent) and one the seller
	has opened but not signed (Viewed). Seeded as if DocuSeal had answered: no real submission exists."""
	import frappe
	from frappe.utils import get_datetime

	signed = [m for m in ctx.mandates if m["status"] == "Signed" and not m["archived"]][:2]
	drafts = [m for m in ctx.mandates if m["status"] == "Draft" and not m["archived"]][:2]
	plan = [(m, "Signed") for m in signed] + [
		(m, state) for m, state in zip(drafts, ("Sent", "Viewed"), strict=False)
	]
	for index, (m, state) in enumerate(plan):
		if frappe.db.get_value("Mandate", m["name"], "signing_status") not in (None, "", "Not sent"):
			continue
		doc = frappe.get_doc("Mandate", m["name"])
		client = frappe.db.get_value("Lead", doc.lead, "client")
		owner = frappe.db.get_value("Client", client, ["client_name", "email"], as_dict=True)
		sent = get_datetime(f"{ctx.today - timedelta(days=9 + index * 2)} 10:30:00")
		viewed = sent + timedelta(hours=3)
		done = sent + timedelta(days=1, hours=2)
		signers = [
			("Seller", owner.client_name, owner.email or f"seller{index}@example.com"),
			("Company", PROFILES[ctx.word]["signer"], f"signer@{ctx.word}.demo.example.com"),
		]
		doc.signing_provider = "DocuSeal"
		doc.docuseal_submission_id = f"{900 + index}"
		doc.signing_status = state
		doc.signing_sent_on = sent
		doc.signing_viewed_on = viewed if state != "Sent" else None
		doc.signing_completed_on = done if state == "Signed" else None
		doc.set("signers", [])
		for role, name, email in signers:
			status = state if role == "Seller" else ("Signed" if state == "Signed" else "Sent")
			doc.append(
				"signers",
				{
					"role": role,
					"signer_name": name,
					"signer_email": email,
					"status": status,
					"submitter_id": f"{1000 + index * 2 + (role == 'Company')}",
					"sent_on": sent,
					"viewed_on": viewed if status in ("Viewed", "Signed") else None,
					"completed_on": done if status == "Signed" else None,
				},
			)
		doc.flags.ignore_permissions = True
		doc.save()
		ctx.count("created", "Mandate signing state")


def _dossier_pdfs(ctx):
	"""The branded Dossier PDF of the first signed mandates, made as the seller's agent."""
	import frappe

	from sellos.inventory import mandates

	signed = [m for m in ctx.mandates if m["status"] == "Signed" and not m["archived"]][:PDF_MANDATES]
	for m in signed:
		if frappe.db.get_value("Mandate", m["name"], "dossier_version"):
			continue
		agent = next((s["agent"] for s in ctx.sellers if s["name"] == m["lead"]), ctx.users["admin"])
		with _as(agent):
			mandates.generate_dossier_pdf(m["name"])
		ctx.count("created", "Dossier PDF")


def _split_deals(ctx):
	"""Deals with one, two and three channel partner splits, dated in every period, approved."""
	import frappe

	from sellos.inventory import api as inventory
	from sellos.inventory import deals

	if frappe.db.exists("Property", {"title": ["like", f"{PROPERTY_PREFIX}%"]}):
		return
	firms = [p["name"] for p in ctx.partners if p.get("status") == "Approved"]
	if len(firms) < 3 or not ctx.leads:
		return
	agents = list(ctx.users["agents"])
	buyers = [row for row in ctx.leads if row.get("client")]
	for row in deal_plan(ctx.today):
		prop = inventory.save_property(
			{
				"title": f"{PROPERTY_PREFIX} {row['ordinal']}",
				"property_type": "Apartment",
				"city": ctx.region["city"],
				"carpet_area": 780 + row["ordinal"] * 15,
			}
		)["name"]
		agent = agents[row["ordinal"] % len(agents)]
		client = buyers[row["ordinal"] % len(buyers)]["client"]
		splits = [{"party_type": "Agent", "agent": agent, "percent": row["agent"]}]
		for n, share in enumerate(row["shares"]):
			splits.append(
				{
					"party_type": "Channel Partner",
					"partner_firm": firms[(row["ordinal"] + n) % len(firms)],
					"percent": share,
				}
			)
		splits.append({"party_type": "Company", "percent": row["company"]})
		name = deals.save_deal(
			{
				"client": client,
				"property": prop,
				"price": row["price"],
				"deal_date": str(row["date"]),
				"commission_amount": round(row["price"] * 0.02),
				"splits": splits,
			}
		)["name"]
		deals.approve_splits(name)
		inventory.set_inventory_status("Property", prop, "Sold", "Sold through the deal")
		ctx.count("created", "Deal")
