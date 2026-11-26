"""The Company Profile (SOS-LOOP, Leads and Sales round): the company's name, logo, colours, RERA number, address,
phone, email, website and footer text, kept in SellOS Settings and used by the dossier PDF and the mandate document.

Only a Company Admin reads or changes it through these methods. The two colours must be readable: the primary
colour carries white text (the cover band and the headings), so it needs a contrast of at least 4.5 to 1 against
white; the accent colour draws rules and highlights, so it needs at least 3 to 1. A colour that fails is refused
with the ratio it got. With nothing set, the documents use a clean default look (DEFAULT_BRAND).
"""

import base64
import binascii
import re
from io import BytesIO

import frappe
from frappe import _
from frappe.utils import validate_email_address

from sellos.access.registry import sellos_api
from sellos.access.roles import COMPANY_ADMIN
from sellos.inventory.base import clean_rera_number, squash

SETTINGS = "SellOS Settings"
DEFAULT_PRIMARY = "#1F3A5F"
DEFAULT_ACCENT = "#B7791F"
MIN_PRIMARY_CONTRAST = 4.5
MIN_ACCENT_CONTRAST = 3.0
LOGO_LIMIT = 1024 * 1024
LOGO_MAX_SIDE = 2000
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_PHONE = re.compile(r"^[0-9+()\s-]{6,25}$")
LIMITS = {"company_name": 80, "address": 300, "footer_text": 200, "website": 120, "city": 60}
FIELDS = (
	"company_name",
	"brand_color",
	"accent_color",
	"rera_number",
	"address",
	"city",
	"contact_phone",
	"contact_email",
	"website",
	"footer_text",
)


def _channel(value: int) -> float:
	v = value / 255
	return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def luminance(colour: str) -> float:
	r, g, b = (int(colour[i : i + 2], 16) for i in (1, 3, 5))
	return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_with_white(colour: str) -> float:
	"""The WCAG contrast ratio of a #RRGGBB colour against white, from 1 to 21."""
	return round(1.05 / (luminance(colour) + 0.05), 2)


def readable_on(colour: str) -> str:
	"""White or near black, whichever reads better on the colour."""
	return "#FFFFFF" if contrast_with_white(colour) >= 4.5 else "#1A1A1A"


def brand() -> dict:
	"""The branding every document uses, with the default look for what is not set."""
	row = frappe._dict({f: frappe.db.get_single_value(SETTINGS, f) for f in (*FIELDS, "logo")})
	primary = row.brand_color if _HEX.match(row.brand_color or "") else DEFAULT_PRIMARY
	accent = row.accent_color if _HEX.match(row.accent_color or "") else DEFAULT_ACCENT
	if contrast_with_white(primary) < MIN_PRIMARY_CONTRAST:
		primary = DEFAULT_PRIMARY  # a colour set before the check existed, too pale for white text
	if contrast_with_white(accent) < MIN_ACCENT_CONTRAST:
		accent = DEFAULT_ACCENT
	return {
		"name": row.company_name or "",
		"logo": row.logo or "",
		"primary": primary,
		"accent": accent,
		"rera_number": row.rera_number or "",
		"address": " ".join(p for p in (row.address, row.city) if p),
		"phone": row.contact_phone or "",
		"email": row.contact_email or "",
		"website": row.website or "",
		"footer": row.footer_text or "",
		"is_default": not (row.company_name or row.logo or row.brand_color),
	}


def file_bytes(url: str) -> bytes | None:
	"""The exact bytes of a stored file, or None when there is none. File.get_content decodes a file that happens to
	read as text, which would change an image's bytes, so it is asked for with no encodings to try."""
	if not url or not frappe.db.exists("File", {"file_url": url}):
		return None
	try:
		# An empty list of encodings returns the bytes as stored, never decoded.
		content = frappe.get_doc("File", {"file_url": url}).get_content(encodings=[])
	except OSError:
		return None
	return content.encode("latin-1") if isinstance(content, str) else content


def logo_bytes(url: str) -> bytes | None:
	"""The logo file's bytes, or None when there is none."""
	return file_bytes(url)


def _profile() -> dict:
	data = brand()
	values = {f: frappe.db.get_single_value(SETTINGS, f) or "" for f in FIELDS}
	return {
		**values,
		"logo": data["logo"],
		"effective_primary": data["primary"],
		"effective_accent": data["accent"],
		"primary_contrast": contrast_with_white(data["primary"]),
		"accent_contrast": contrast_with_white(data["accent"]),
		"min_primary_contrast": MIN_PRIMARY_CONTRAST,
		"min_accent_contrast": MIN_ACCENT_CONTRAST,
		"default_primary": DEFAULT_PRIMARY,
		"default_accent": DEFAULT_ACCENT,
	}


@sellos_api(COMPANY_ADMIN)
def get_company_profile():
	"""The company profile and the contrast of its colours."""
	return _profile()


def _check(values: dict) -> dict:
	out = {}
	for field in FIELDS:
		if field not in values:
			continue
		value = squash(values[field]) if field != "address" else " ".join(str(values[field] or "").split())
		if len(value) > LIMITS.get(field, 200):
			frappe.throw(_("{0} is too long.").format(field.replace("_", " ")))
		out[field] = value
	for field, minimum, label in (
		("brand_color", MIN_PRIMARY_CONTRAST, _("Primary colour")),
		("accent_color", MIN_ACCENT_CONTRAST, _("Accent colour")),
	):
		colour = out.get(field)
		if not colour:
			continue
		if not _HEX.match(colour):
			frappe.throw(_("{0} is a colour such as #1F3A5F.").format(label))
		ratio = contrast_with_white(colour)
		if ratio < minimum:
			frappe.throw(
				_(
					"{0} is too pale to read: its contrast against white is {1} to 1 and it needs at least {2} to 1."
				).format(label, ratio, minimum)
			)
	if out.get("rera_number"):
		out["rera_number"] = clean_rera_number(out["rera_number"])
	if out.get("contact_phone") and not _PHONE.match(out["contact_phone"]):
		frappe.throw(_("Enter the phone number with digits, spaces, + and - only."))
	if out.get("contact_email") and not validate_email_address(out["contact_email"]):
		frappe.throw(_("Enter a valid email address."))
	if out.get("website") and not re.match(r"^https?://[^\s]+$", out["website"]):
		frappe.throw(_("Enter the website as an address starting with http:// or https://."))
	return out


@sellos_api(COMPANY_ADMIN)
def save_company_profile(values):
	"""Save the company profile. The colours are checked for contrast; an empty colour returns to the default."""
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	clean = _check(values)
	doc = frappe.get_doc(SETTINGS)
	for field, value in clean.items():
		doc.set(field, value)
	doc.flags.ignore_permissions = True  # the caller is a Company Admin, checked by the declaration
	doc.save()
	frappe.clear_document_cache(SETTINGS, SETTINGS)
	return _profile()


@sellos_api(COMPANY_ADMIN)
def upload_company_logo(filename, content_base64):
	"""Set the logo: a PNG or JPG of up to 1 MB and 2000 pixels a side, checked by opening it."""
	from PIL import Image, UnidentifiedImageError

	try:
		content = base64.b64decode(str(content_base64 or ""), validate=True)
	except (binascii.Error, ValueError):
		frappe.throw(_("The logo could not be read. Choose it again."))
	if not content or len(content) > LOGO_LIMIT:
		frappe.throw(_("The logo is a PNG or JPG of up to 1 MB."))
	try:
		with Image.open(BytesIO(content)) as image:
			image.verify()
			fmt, size = image.format, image.size
	except (UnidentifiedImageError, OSError, SyntaxError):
		frappe.throw(_("The logo must be a PNG or JPG image."))
	if fmt not in ("PNG", "JPEG") or max(size) > LOGO_MAX_SIDE:
		frappe.throw(_("The logo is a PNG or JPG of up to {0} pixels a side.").format(LOGO_MAX_SIDE))
	ext = "png" if fmt == "PNG" else "jpg"
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"company-logo-{frappe.generate_hash(length=6)}.{ext}",
			"content": content,
			"is_private": 0,
			"attached_to_doctype": SETTINGS,
			"attached_to_name": SETTINGS,
			"attached_to_field": "logo",
		}
	)
	file.flags.ignore_permissions = True
	file.insert()
	doc = frappe.get_doc(SETTINGS)
	doc.logo = file.file_url
	doc.flags.ignore_permissions = True
	doc.save()
	frappe.clear_document_cache(SETTINGS, SETTINGS)
	return _profile()
