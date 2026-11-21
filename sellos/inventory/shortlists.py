"""Shortlists and sharing with buyers (SOS-P7-09).

A shortlist is a list of listings and units for one client, made by an agent (Jayman, SOS-SETUP-34 question 11).
The agent puts homes on it from the matches of SOS-P7-08, orders them and adds a note to each. Sharing marks the
shortlist shared and tells the client, by a link to their own client view (which they open after signing in) or
by a PDF with the company's branding, the photos (Media Assets) and the prices.

* A client is the user whose email is the email of a Client record. They see only the shortlists made for that
  record that were shared, never a draft, and never another client's. The link and the PDF hold the agent's
  name and phone number and no other phone number.
* Every time a client opens an item, the item keeps the first time, the last time and a count, and the agent
  sees them.
* An item whose listing is unpublished or archived, or whose unit or property is no longer Available, is marked
  on the shortlist (for the agent and for the client). It is not removed.
* A user reads the shortlists of their own, a Sales Manager the shortlists of its team's agents, and a Company
  Admin all of them. Nothing is deleted: a shortlist is archived, which hides it from the client.
"""

import base64
import io

import frappe
from frappe import _
from frappe.utils import cint, escape_html, flt, now_datetime

from sellos.access import lead_permissions as perms
from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, CLIENT, COMPANY_ADMIN, SALES_MANAGER
from sellos.inventory import matching
from sellos.inventory.base import AVAILABLE
from sellos.sellos.doctype.shortlist.shortlist import MAX_ITEMS, clean_note

READERS = (COMPANY_ADMIN, AGENT, SALES_MANAGER)
EDITORS = (COMPANY_ADMIN, AGENT)
DOCTYPE = "Shortlist"
KINDS = ("Unit", "Listing")
VIA = ("Link", "PDF")
CLIENT_PATH = "/sellos/client/shortlists"
PHOTOS_SHOWN = 6
PHOTOS_IN_PDF = 2
THUMB = (640, 480)


# --- who sees which shortlist -----------------------------------------------------------------------------


def get_permission_query_conditions(user=None):
	"""An agent reads the shortlists they made, a Sales Manager their team's, a Company Admin all (a client reads
	theirs only through the client methods below, never through the list)."""

	def build(user, scope):
		users = perms.visible_users(user, scope)
		return perms._in_sql(f"`tab{DOCTYPE}`.`agent`", users)

	return perms._conditions(user, build)


def has_permission(doc, ptype=None, user=None, **kwargs):
	user, scope = perms._scope(user)
	if scope not in ("own", "team"):
		return perms._without_own(scope, ptype)
	if ptype == "create":
		return True  # the doctype's role rows decide who may create
	return doc.get("agent") in perms.visible_users(user, scope)


# --- what an item shows ------------------------------------------------------------------------------------


def _photo_urls(listings) -> dict[str, list[str]]:
	"""Each listing's photos (public file URLs) in the listing's order. A video or an archived asset is left out."""
	if not listings:
		return {}
	rows = frappe.get_all(
		"Listing Media",
		filters={"parenttype": "Listing", "parent": ["in", list(listings)]},
		fields=["parent", "media_asset"],
		order_by="parent, idx",
	)
	assets = {
		a.name: a.file
		for a in frappe.get_all(
			"Media Asset",
			filters={
				"name": ["in", [r.media_asset for r in rows] or [""]],
				"media_type": "Photo",
				"archived": 0,
			},
			fields=["name", "file"],
		)
	}
	found: dict[str, list[str]] = {}
	for row in rows:
		if assets.get(row.media_asset):
			found.setdefault(row.parent, []).append(assets[row.media_asset])
	return found


def _facts(rows) -> dict:
	"""What each item shows, worked out for all the rows with a handful of queries. Returns row name -> dict."""
	unit_names = {r.unit for r in rows if r.kind == "Unit" and r.unit}
	listing_names = {r.listing for r in rows if r.kind == "Listing" and r.listing}
	listings = {
		row.name: row
		for row in frappe.get_all(
			"Listing",
			filters={"name": ["in", list(listing_names) or [""]]},
			fields=[
				"name",
				"title",
				"unit",
				"property",
				"asking_price",
				"description",
				"published",
				"archived",
			],
		)
	}
	unit_names |= {row.unit for row in listings.values() if row.unit}
	property_names = {row.property for row in listings.values() if row.property}
	units = {
		row.name: row
		for row in frappe.get_all(
			"Unit",
			filters={"name": ["in", list(unit_names) or [""]]},
			fields=[
				"name",
				"unit_number",
				"project",
				"configuration",
				"carpet_area",
				"floor",
				"parking",
				"status",
				"archived",
			],
		)
	}
	properties = {
		row.name: row
		for row in frappe.get_all(
			"Property",
			filters={"name": ["in", list(property_names) or [""]]},
			fields=[
				"name",
				"property_type",
				"locality",
				"configuration",
				"carpet_area",
				"status",
				"archived",
			],
		)
	}
	projects = {
		p.name: p
		for p in frappe.get_all(
			"Project",
			filters={"name": ["in", list({u.project for u in units.values()} or [""])]},
			fields=["name", "project_name", "locality"],
		)
	}
	prices = matching._unit_prices(list(units.values()))
	# A unit with no listing of its own shows the photos of a published listing of that unit.
	of_unit = {}
	for row in frappe.get_all(
		"Listing",
		filters={"unit": ["in", list(unit_names) or [""]], "published": 1, "archived": 0},
		fields=["name", "unit"],
		order_by="creation",
	):
		of_unit.setdefault(row.unit, row.name)
	photos = _photo_urls(set(listing_names) | set(of_unit.values()))

	def unit_state(unit):
		if not unit or unit.archived or unit.status != AVAILABLE:
			return _("No longer available") + (f" ({unit.status})" if unit and not unit.archived else "")
		return ""

	def unit_facts(unit):
		project = projects.get(unit.project)
		return {
			"title": f"{project.project_name if project else unit.project}, unit {unit.unit_number}",
			"configuration": unit.configuration or "",
			"locality": (project.locality if project else "") or "",
			"property_type": matching.UNIT_TYPE,
			"carpet_area": flt(unit.carpet_area),
			"price": prices.get(unit.name) or 0,
		}

	found = {}
	for row in rows:
		if row.kind == "Unit":
			unit = units.get(row.unit)
			facts = (
				unit_facts(unit)
				if unit
				else {"title": row.unit, "configuration": "", "locality": "", "property_type": ""}
			)
			facts.update(
				target=row.unit,
				reason=unit_state(unit),
				description="",
				photos=photos.get(of_unit.get(row.unit), []),
			)
		else:
			listing = listings.get(row.listing)
			if not listing:
				facts = {"title": row.listing, "target": row.listing, "reason": _("Unpublished")}
				facts.update(
					configuration="", locality="", property_type="", price=0, photos=[], description=""
				)
			else:
				if listing.unit and units.get(listing.unit):
					facts = unit_facts(units[listing.unit])
					state = unit_state(units[listing.unit])
				else:
					prop = properties.get(listing.property)
					facts = {
						"configuration": (prop.configuration if prop else "") or "",
						"locality": (prop.locality if prop else "") or "",
						"property_type": (prop.property_type if prop else "") or "",
						"carpet_area": flt(prop.carpet_area) if prop else 0,
						"price": 0,
					}
					state = (
						""
						if prop and not prop.archived and prop.status == AVAILABLE
						else _("No longer available")
						+ (f" ({prop.status})" if prop and not prop.archived else "")
					)
				facts.update(
					title=listing.title,
					target=listing.name,
					price=cint(flt(listing.asking_price)) or facts.get("price") or 0,
					description=listing.description or "",
					photos=photos.get(listing.name, []),
					reason=(_("Unpublished") if not listing.published or listing.archived else state),
				)
		facts["unavailable"] = bool(facts["reason"])
		found[row.name] = facts
	return found


def _item_views(doc, for_agent) -> list[dict]:
	facts = _facts(list(doc.items))
	views = []
	for position, row in enumerate(doc.items, 1):
		fact = facts[row.name]
		view = {
			"name": row.name,
			"position": position,
			"kind": row.kind,
			"target": fact["target"],
			"title": fact["title"],
			"configuration": fact["configuration"],
			"locality": fact["locality"],
			"property_type": fact["property_type"],
			"carpet_area": fact.get("carpet_area") or 0,
			"price": fact["price"] or 0,
			"note": row.note or "",
			"description": fact["description"],
			"photos": fact["photos"][:PHOTOS_SHOWN],
			"unavailable": fact["unavailable"],
			"reason": fact["reason"],
		}
		if for_agent:
			view["opened"] = {
				"count": cint(row.open_count),
				"first": str(row.first_opened_on or ""),
				"last": str(row.last_opened_on or ""),
			}
		views.append(view)
	return views


def _full_name(user) -> str:
	return frappe.db.get_value("User", user, "full_name") or user or ""


def _shortlist_view(doc) -> dict:
	items = _item_views(doc, for_agent=True)
	roles = frappe.get_roles()
	return {
		"name": doc.name,
		"title": doc.title,
		"client": doc.client,
		"client_name": frappe.db.get_value("Client", doc.client, "client_name") or doc.client,
		"lead": doc.lead or "",
		"agent": doc.agent,
		"agent_name": _full_name(doc.agent),
		"note": doc.note or "",
		"items": items,
		"item_count": len(items),
		"unavailable_count": sum(1 for i in items if i["unavailable"]),
		"opened_count": sum(1 for i in items if i["opened"]["count"]),
		"shared": bool(doc.shared_on),
		"shared_on": str(doc.shared_on or ""),
		"shared_via": doc.shared_via or "",
		"share_count": cint(doc.share_count),
		"client_last_opened_on": str(doc.client_last_opened_on or ""),
		"archived": bool(doc.archived),
		"can_edit": any(role in roles for role in EDITORS) and not doc.archived,
		"max_items": MAX_ITEMS,
	}


def _row_view(doc) -> dict:
	return {
		"name": doc.name,
		"title": doc.title,
		"client": doc.client,
		"client_name": frappe.db.get_value("Client", doc.client, "client_name") or doc.client,
		"lead": doc.lead or "",
		"agent_name": _full_name(doc.agent),
		"item_count": frappe.db.count("Shortlist Item", {"parent": doc.name, "parenttype": DOCTYPE}),
		"shared": bool(doc.shared_on),
		"shared_on": str(doc.shared_on or ""),
		"archived": bool(doc.archived),
		"modified": str(doc.modified),
	}


def _get(name, write=False):
	if not name or not frappe.db.exists(DOCTYPE, name):
		frappe.throw(_("There is no shortlist {0}.").format(name), frappe.DoesNotExistError)
	doc = frappe.get_doc(DOCTYPE, name)
	doc.check_permission("write" if write else "read")
	if write and doc.archived:
		frappe.throw(_("An archived shortlist can not be changed. Restore it first."))
	return doc


def _row(doc, item):
	row = next((r for r in doc.items if r.name == item), None)
	if row is None:
		frappe.throw(_("That home is not on the shortlist."), frappe.DoesNotExistError)
	return row


def _save(doc) -> dict:
	doc.save()
	doc.reload()
	return _shortlist_view(doc)


# --- the agent's methods -----------------------------------------------------------------------------------


@sellos_api(*READERS)
def list_shortlists(lead="", client="", include_archived=0):
	"""The shortlists the caller may see, newest first, optionally of one lead or one client."""
	filters = {}
	if lead:
		filters["lead"] = lead
	if client:
		filters["client"] = client
	if not cint(include_archived):
		filters["archived"] = 0
	docs = frappe.get_list(
		DOCTYPE,
		filters=filters,
		fields=["name", "title", "client", "lead", "agent", "shared_on", "archived", "modified"],
		order_by="modified desc",
		limit_page_length=200,
	)
	return {"shortlists": [_row_view(frappe._dict(d)) for d in docs]}


@sellos_api(*READERS)
def get_shortlist(name):
	"""One shortlist with its homes in order, their prices, photos, notes, what is no longer available, and which
	ones the client opened and when."""
	return _shortlist_view(_get(name))


@sellos_api(*EDITORS)
def create_shortlist(client="", lead="", title="", note=""):
	"""Make an empty shortlist for one client (or for the lead's client)."""
	if lead:
		if not frappe.db.exists("Lead", lead):
			frappe.throw(_("There is no lead {0}.").format(lead), frappe.DoesNotExistError)
		lead_doc = frappe.get_doc("Lead", lead)
		lead_doc.check_permission("read")
		client = client or lead_doc.client
	if not client or not frappe.db.exists("Client", client):
		frappe.throw(_("Choose the client the shortlist is for."), frappe.DoesNotExistError)
	client_doc = frappe.get_doc("Client", client)
	client_doc.check_permission("read")
	if client_doc.archived:
		frappe.throw(_("That client is archived."))
	doc = frappe.get_doc(
		{
			"doctype": DOCTYPE,
			"title": " ".join(str(title or "").split()) or _("Homes for {0}").format(client_doc.client_name),
			"client": client,
			"lead": lead or None,
			"note": note,
		}
	)
	doc.insert()
	return _shortlist_view(doc)


@sellos_api(*EDITORS)
def update_shortlist(name, title=None, note=None):
	"""Change the title or the note to the buyer."""
	doc = _get(name, write=True)
	if title is not None:
		doc.title = title
	if note is not None:
		doc.note = note
	return _save(doc)


def _offerable(kind, target) -> None:
	"""Only an Available unit or a published listing of an Available unit or property goes on a shortlist."""
	if kind not in KINDS:
		frappe.throw(_("A home is a unit or a listing."))
	if not target or not frappe.db.exists(kind, target):
		frappe.throw(_("There is no {0} {1}.").format(_(kind).lower(), target), frappe.DoesNotExistError)
	frappe.has_permission(kind, "read", doc=target, throw=True)
	row = frappe._dict(name="x", kind=kind, unit=target if kind == "Unit" else None)
	row.listing = target if kind == "Listing" else None
	if _facts([row])["x"]["unavailable"]:
		frappe.throw(_("Only an Available unit or a published listing goes on a shortlist."))


def _shortlist_of_lead(lead) -> str:
	"""The caller's latest open shortlist of the lead's client, made when there is none."""
	found = frappe.get_all(
		DOCTYPE,
		filters={"lead": lead, "agent": frappe.session.user, "archived": 0},
		order_by="creation desc",
		limit=1,
		pluck="name",
	)
	return found[0] if found else create_shortlist(lead=lead)["name"]


@sellos_api(*EDITORS)
def add_to_shortlist(kind, target, shortlist="", lead="", note=""):
	"""Put a unit or a listing last on a shortlist. Without a shortlist, `lead` picks the caller's open shortlist
	for that lead's client, and makes one when there is none. A home already on it is left where it is."""
	_offerable(kind, target)
	if not shortlist and not lead:
		frappe.throw(_("Choose the shortlist, or the lead to make one for."))
	doc = _get(shortlist or _shortlist_of_lead(lead), write=True)
	if any((r.kind, r.unit if r.kind == "Unit" else r.listing) == (kind, target) for r in doc.items):
		return {**_shortlist_view(doc), "added": False}
	doc.append("items", {"kind": kind, kind.lower(): target, "note": note})
	return {**_save(doc), "added": True}


@sellos_api(*EDITORS)
def save_item_note(name, item, note):
	"""Set the note to the buyer on one home."""
	doc = _get(name, write=True)
	_row(doc, item).note = note
	return _save(doc)


@sellos_api(*EDITORS)
def remove_shortlist_item(name, item):
	"""Take a home off the shortlist. A home not on it is left alone."""
	doc = _get(name, write=True)
	if any(r.name == item for r in doc.items):
		doc.set("items", [r for r in doc.items if r.name != item])
		return _save(doc)
	return _shortlist_view(doc)


@sellos_api(*EDITORS)
def reorder_shortlist(name, order):
	"""Set the order of the homes. `order` lists every item's name once."""
	doc = _get(name, write=True)
	order = frappe.parse_json(order) if isinstance(order, str) else (order or [])
	by_name = {r.name: r for r in doc.items}
	if sorted(order) != sorted(by_name):
		frappe.throw(_("The order must list each home of the shortlist once."))
	if order != [r.name for r in doc.items]:
		doc.set("items", [by_name[n] for n in order])
		for position, row in enumerate(doc.items, 1):
			row.idx = position  # append keeps a row's old position
		return _save(doc)
	return _shortlist_view(doc)


@sellos_api(*EDITORS)
def archive_shortlist(name, archived=1):
	"""Archive a shortlist (the client no longer sees it) or restore it. Nothing is deleted."""
	doc = _get(name)
	doc.check_permission("write")
	doc.archived = 1 if cint(archived) else 0
	return _save(doc)


# --- sharing -----------------------------------------------------------------------------------------------


def client_link(name) -> str:
	return frappe.utils.get_url(f"{CLIENT_PATH}/{name}")


def pdf_path(name, mine=False) -> str:
	method = "my_shortlist_pdf" if mine else "shortlist_pdf"
	return f"/api/method/sellos.inventory.shortlists.{method}?name={name}"


def _email_client(doc, via) -> tuple[bool, bool]:
	"""(has an email, sent). The mail holds the link and, for a PDF, the PDF: nothing of any other client."""
	from sellos.access.users import mail_ready

	email = frappe.db.get_value("Client", doc.client, "email")
	if not email:
		return False, False
	if not mail_ready():
		return True, False
	company = frappe.db.get_single_value("SellOS Settings", "company_name") or "SellOS"
	agent = escape_html(_full_name(doc.agent))
	link = client_link(doc.name)
	message = _(
		"Hello,<br><br>{0} at {1} has chosen homes for you. Open this link and sign in to see them:"
		"<br><br><a href='{2}'>{2}</a>"
	).format(agent, escape_html(company), link)
	options = {}
	if via == "PDF":
		options["attachments"] = [{"fname": f"{doc.name}.pdf", "fcontent": _pdf_bytes(doc)}]
	try:
		frappe.sendmail(
			recipients=[email],
			subject=_("Homes chosen for you by {0}").format(company),
			message=message,
			now=True,
			**options,
		)
	except Exception:
		frappe.log_error("Shortlist email failed")
		return True, False
	return True, True


@sellos_api(*EDITORS)
def share_shortlist(name, via="Link"):
	"""Share the shortlist with its client, as a link to their client view or as a PDF. The client is emailed when
	the client has an email address and this site can send mail; the answer says whether that happened. Sharing
	again sends it again and counts it."""
	if via not in VIA:
		frappe.throw(_("Share a shortlist as a link or as a PDF."))
	doc = _get(name, write=True)
	if not doc.items:
		frappe.throw(_("Put at least one home on the shortlist before you share it."))
	doc.shared_on = now_datetime()
	doc.shared_by = frappe.session.user
	doc.shared_via = via
	doc.share_count = cint(doc.share_count) + 1
	view = _save(doc)
	has_email, emailed = _email_client(doc, via)
	return {
		"shortlist": view,
		"via": via,
		"link": client_link(doc.name),
		"pdf": pdf_path(doc.name) if via == "PDF" else "",
		"client_has_email": has_email,
		"emailed": emailed,
	}


# --- the PDF -----------------------------------------------------------------------------------------------


def _agent_contact(user) -> dict:
	row = frappe.db.get_value("User", user, ["full_name", "mobile_no", "email"], as_dict=True) or {}
	return {"name": row.get("full_name") or user, "phone": row.get("mobile_no") or ""}


def _thumbnail(url) -> str:
	"""A photo as a small JPEG data URI for the PDF, or "" when it can not be read."""
	from PIL import Image

	if not url or not frappe.db.exists("File", {"file_url": url}):
		return ""
	try:
		content = frappe.get_doc("File", {"file_url": url}).get_content()
		if isinstance(content, str):
			content = content.encode()
		with Image.open(io.BytesIO(content)) as picture:
			picture = picture.convert("RGB")
			picture.thumbnail(THUMB)
			out = io.BytesIO()
			picture.save(out, "JPEG", quality=75)
	except Exception:
		return ""
	return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()


def pdf_view(doc) -> dict:
	"""What the PDF shows: the company's branding, the client's own shortlist, the agent's name and phone, and
	each home with its price and its first photos."""
	from sellos.inventory import cost_sheet

	items = _item_views(doc, for_agent=False)
	for item in items:
		item["pictures"] = [p for p in (_thumbnail(u) for u in item["photos"][:PHOTOS_IN_PDF]) if p]
	return {
		"name": doc.name,
		"title": doc.title,
		"client_name": frappe.db.get_value("Client", doc.client, "client_name") or "",
		"note": doc.note or "",
		"made_on": str(doc.shared_on or now_datetime())[:10],
		"agent": _agent_contact(doc.agent),
		"brand": cost_sheet._brand(),
		"items": items,
	}


def shortlist_html(view) -> str:
	from sellos.inventory import cost_sheet

	e = escape_html
	brand = view["brand"]
	logo = cost_sheet._logo_data_uri(brand["logo"])
	contact = " | ".join(p for p in (brand["phone"], brand["email"]) if p)
	agent = view["agent"]
	agent_line = " | ".join(p for p in (agent["name"], agent["phone"]) if p)

	def item(i):
		price = cost_sheet.inr(i["price"]) if i["price"] else _("Price on request")
		facts = " | ".join(
			str(p)
			for p in (
				i["configuration"],
				i["locality"],
				f"{i['carpet_area']:g} sq ft" if i["carpet_area"] else "",
			)
			if p
		)
		pictures = "".join(f'<img class="pic" src="{p}">' for p in i["pictures"])
		flag = f'<div class="flag">{e(i["reason"])}</div>' if i["unavailable"] else ""
		note = f'<div class="note">{e(i["note"])}</div>' if i["note"] else ""
		return (
			f'<div class="item"><div class="pics">{pictures}</div><div class="text">'
			f'<div class="t">{i["position"]}. {e(i["title"])}</div><div class="price">{e(price)}</div>'
			f'<div class="small">{e(facts)}</div>{flag}{note}</div></div>'
		)

	return f"""<html><head><meta charset="utf-8"><style>
body {{ font-family: Helvetica, Arial, sans-serif; font-size: 12px; color: #222; }}
.head {{ border-bottom: 3px solid {brand["colour"]}; padding-bottom: 8px; margin-bottom: 14px; }}
.head img {{ height: 40px; vertical-align: middle; margin-right: 10px; }}
.head .name {{ font-size: 20px; font-weight: bold; color: {brand["colour"]}; vertical-align: middle; }}
.small {{ color: #555; font-size: 11px; }}
h1 {{ font-size: 16px; color: {brand["colour"]}; margin: 6px 0; }}
.item {{ border: 1px solid #ddd; padding: 8px; margin-bottom: 10px; page-break-inside: avoid; overflow: hidden; }}
.pics {{ float: left; width: 210px; }} .pic {{ width: 100px; height: 75px; margin: 0 4px 4px 0; }}
.text {{ margin-left: 215px; }} .t {{ font-size: 13px; font-weight: bold; }}
.price {{ color: {brand["colour"]}; font-weight: bold; margin: 2px 0; }}
.flag {{ color: #b00020; font-weight: bold; margin-top: 3px; }} .note {{ margin-top: 4px; font-style: italic; }}
</style></head><body>
<div class="head">{f'<img src="{logo}">' if logo else ""}<span class="name">{e(brand["name"])}</span>
<div class="small">{e(contact)}</div><div class="small">{e(brand["address"])}</div></div>
<h1>{e(view["title"])}</h1>
<div class="small">{e(_("Chosen for {0} on {1}").format(view["client_name"], view["made_on"]))}</div>
<div class="small">{e(_("Your contact"))}: {e(agent_line)}</div>
{f"<p>{e(view['note'])}</p>" if view["note"] else ""}
{"".join(item(i) for i in view["items"])}
<p class="small">{e(_("Prices are in rupees and may change. A home marked as no longer available is not on offer."))}</p>
</body></html>"""


def _pdf_bytes(doc) -> bytes:
	from frappe.utils.pdf import get_pdf

	from sellos.inventory.cost_sheet import inr
	from sellos.inventory.plain_pdf import build_shortlist_pdf

	view = pdf_view(doc)
	try:
		return get_pdf(shortlist_html(view))
	except OSError:
		# The page layout program is not installed on this machine: write the same lines plainly.
		return build_shortlist_pdf(view, inr)


def _send_pdf(doc):
	frappe.local.response.filename = f"{doc.name}.pdf"
	frappe.local.response.filecontent = _pdf_bytes(doc)
	frappe.local.response.type = "pdf"


@sellos_api(*READERS)
def shortlist_pdf(name):
	"""The shortlist as the client gets it, as a PDF with the company's branding, the photos and the prices."""
	_send_pdf(_get(name))


# --- the client's methods ----------------------------------------------------------------------------------


def my_clients(user=None) -> list[str]:
	"""The Client records whose email is the signed in user's."""
	user = user or frappe.session.user
	return frappe.get_all("Client", filters={"email": user, "archived": 0}, pluck="name")


def _mine(name):
	"""A shortlist shared with the signed in client. Missing, a draft, archived and another client's read the same."""
	doc = frappe.get_doc(DOCTYPE, name) if name and frappe.db.exists(DOCTYPE, name) else None
	if not doc or doc.archived or not doc.shared_on or doc.client not in my_clients():
		frappe.throw(_("This shortlist is not yours."), frappe.PermissionError)
	return doc


def _client_view(doc) -> dict:
	return {
		"name": doc.name,
		"title": doc.title,
		"note": doc.note or "",
		"shared_on": str(doc.shared_on or ""),
		"agent": _agent_contact(doc.agent),
		"items": _item_views(doc, for_agent=False),
		"pdf": pdf_path(doc.name, mine=True),
	}


@sellos_api(CLIENT)
def my_shortlists():
	"""The shortlists shared with the signed in client, newest first."""
	clients = my_clients()
	if not clients:
		return {"shortlists": []}
	rows = frappe.get_all(
		DOCTYPE,
		filters={"client": ["in", clients], "archived": 0, "shared_on": ["is", "set"]},
		fields=["name", "title", "agent", "shared_on", "note"],
		order_by="shared_on desc",
	)
	return {
		"shortlists": [
			{
				"name": r.name,
				"title": r.title,
				"agent_name": _full_name(r.agent),
				"shared_on": str(r.shared_on),
				"note": r.note or "",
				"item_count": frappe.db.count("Shortlist Item", {"parent": r.name, "parenttype": DOCTYPE}),
			}
			for r in rows
		]
	}


@sellos_api(CLIENT)
def my_shortlist(name):
	"""One of the client's own shortlists: the homes in order, prices, photos, notes, what is no longer available,
	and the agent's name and phone."""
	doc = _mine(name)
	doc.db_set("client_last_opened_on", now_datetime(), update_modified=False)
	return _client_view(doc)


@sellos_api(CLIENT)
def open_shortlist_item(name, item):
	"""The client opens one home. The item keeps the first and the last time and how many times, for the agent."""
	doc = _mine(name)
	row = _row(doc, item)
	doc.note_opened(row)
	return next(i for i in _client_view(doc)["items"] if i["name"] == item)


@sellos_api(CLIENT)
def my_shortlist_pdf(name):
	"""The client's own shortlist as a PDF."""
	_send_pdf(_mine(name))
