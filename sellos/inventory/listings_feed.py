"""The listings endpoint (SOS-P4-08).

The company's website reads its published listings here with the "Listings read" key (a scope of the per
company key record, SOS-P1-09: no second key store). `published_listings` is a public listings feed
(`sellos.access.public_listings`): it only reads, returns only published listings and only the fields in
`FIELD_ALLOWLIST`, and the shared checks (key in a header, one short refusal, limits per key and per
tenant, page cap, ETag) run before it. A change to a published listing is announced to the website by the
signed webhook in `sellos.inventory.listing_webhook`.

A Company Admin makes or rotates the key and sets the webhook address in the web app. Both secrets are
shown once, when made.
"""

import frappe
from frappe.utils import get_url

from sellos.access import intake_keys
from sellos.access.public_listings import KEY_HEADER, public_listings
from sellos.access.registry import sellos_api
from sellos.access.roles import COMPANY_ADMIN
from sellos.inventory import listing_webhook

FEED_PATH = "/api/method/sellos.inventory.listings_feed.published_listings"
MAX_PAGE_SIZE = 50
PER_KEY_PER_MINUTE = 120
PER_TENANT_PER_MINUTE = 600

# The only fields a listing leaves with. A new one is added here on purpose, never by default. Never the
# owner or seller, a phone number, a mandate or dossier file, an internal note, who published it or the
# change history, and never media that is not a photo or video of this listing.
FIELD_ALLOWLIST = (
	"id",
	"title",
	"listing_type",
	"asking_price",
	"description",
	"published_on",
	"modified",
	"project",
	"property_type",
	"city",
	"locality",
	"configuration",
	"carpet_area",
	"floor",
	"parking",
	"media",
)


def _media(doc) -> list[dict]:
	out = []
	for row in doc.media:
		asset = frappe.db.get_value(
			"Media Asset", row.media_asset, ["title", "media_type", "file", "archived"], as_dict=True
		)
		if asset and not asset.archived and asset.file:
			out.append({"title": asset.title, "media_type": asset.media_type, "url": asset.file})
	return out


def _place(doc) -> dict:
	"""What the listing offers, in the allowlisted words only."""
	if doc.unit:
		unit = frappe.db.get_value(
			"Unit", doc.unit, ["project", "configuration", "carpet_area", "floor", "parking"], as_dict=True
		)
		project = frappe.db.get_value(
			"Project", unit.project, ["project_name", "city", "locality"], as_dict=True
		)
		return {
			"project": project.project_name,
			"property_type": "",
			"city": project.city or "",
			"locality": project.locality or "",
			"configuration": unit.configuration or "",
			"carpet_area": unit.carpet_area or 0,
			"floor": unit.floor or 0,
			"parking": unit.parking or 0,
		}
	prop = frappe.db.get_value(
		"Property",
		doc.property,
		["property_type", "city", "locality", "configuration", "carpet_area", "floor", "parking"],
		as_dict=True,
	)
	return {
		"project": "",
		"property_type": prop.property_type or "",
		"city": prop.city or "",
		"locality": prop.locality or "",
		"configuration": prop.configuration or "",
		"carpet_area": prop.carpet_area or 0,
		"floor": prop.floor or 0,
		"parking": prop.parking or 0,
	}


def _row(doc) -> dict:
	return {
		"id": doc.name,
		"title": doc.title,
		"listing_type": doc.listing_type,
		"asking_price": doc.asking_price or 0,
		"description": doc.description or "",
		"published_on": str(doc.published_on or ""),
		"modified": str(doc.modified),
		**_place(doc),
		"media": _media(doc),
	}


@public_listings(
	field_allowlist=FIELD_ALLOWLIST,
	max_page_size=MAX_PAGE_SIZE,
	rate_limit_per_key=PER_KEY_PER_MINUTE,
	rate_limit_per_tenant=PER_TENANT_PER_MINUTE,
)
def published_listings(start: int, page_size: int) -> list[dict]:
	"""One page of the company's published listings, oldest published first."""
	names = frappe.get_all(
		"Listing",
		filters={"published": 1, "archived": 0},
		pluck="name",
		order_by="published_on asc, name asc",
		limit_start=start,
		limit_page_length=page_size,
	)
	return [_row(frappe.get_doc("Listing", name)) for name in names]


# --- a Company Admin's view of the endpoint ----------------------------------------------------------------


def _settings(key=None, secret=None) -> dict:
	url, stored_secret = listing_webhook.settings()
	out = {
		"endpoint": f"{get_url()}{FEED_PATH}",
		"key_header": KEY_HEADER,
		"keys": intake_keys.active_keys(intake_keys.LISTINGS_READ),
		"webhook_url": url,
		"webhook_secret_set": bool(stored_secret),
	}
	if key:
		out["key"] = key  # shown once: only its hash is kept
	if secret:
		out["webhook_secret"] = secret  # shown once
	return out


@sellos_api(COMPANY_ADMIN)
def get_listings_feed_settings():
	"""The feed address, the Listings read keys made so far (label and state only, never a key) and the
	change webhook address."""
	return _settings()


@sellos_api(COMPANY_ADMIN)
def rotate_listings_key():
	"""Make a new Listings read key and switch off the old ones. The new key is in the answer once."""
	return _settings(key=intake_keys.make_key(intake_keys.LISTINGS_READ, "Website listings", replace=True))


@sellos_api(COMPANY_ADMIN)
def save_listings_webhook(url="", rotate_secret=0):
	"""Set the https address the website is told about changes at ("" switches the webhook off). A signing
	secret is made when there is none, or when rotate_secret is set, and is in the answer once."""
	url = (url or "").strip()
	if url:
		listing_webhook.check_url(url)
	doc = frappe.get_doc(listing_webhook.SETTINGS)
	doc.set(listing_webhook.URL_FIELD, url)
	secret = None
	if url and (str(rotate_secret).lower() in ("1", "true", "yes") or not listing_webhook.settings()[1]):
		secret = frappe.generate_hash(length=40)
		doc.set(listing_webhook.SECRET_FIELD, secret)
	if not url:
		doc.set(listing_webhook.SECRET_FIELD, "")
	doc.flags.ignore_permissions = True
	doc.save()
	return _settings(secret=secret)
