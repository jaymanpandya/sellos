"""Photos and videos of a listing (SOS-P4-03).

The asset library is the company's uploaded files (Jayman, SOS-SETUP-34): each photo or video is a Media Asset
that keeps its file, title, type and size. A listing links assets from the library, in an order a person can
change, and one asset may be on several listings. A Company Admin or an Agent uploads and links; a Sales
Manager reads. Every file is checked before it is stored: its extension and its first bytes must agree on a
known photo or video type, and a photo may be up to 5 MB and a video up to 20 MB. Photos and videos are public
files, because the website shows them once a listing is published, and are named with a random name so an
unpublished listing's pictures can not be guessed. Nothing is deleted: removing a file from a listing unlinks
it, and the asset stays in the library.
"""

import base64
import binascii
import io
import secrets

import frappe
from frappe import _
from PIL import Image

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN, SALES_MANAGER
from sellos.inventory.base import squash

READERS = (COMPANY_ADMIN, AGENT, SALES_MANAGER)
EDITORS = (COMPANY_ADMIN, AGENT)

PHOTO_LIMIT = 5 * 1024 * 1024
VIDEO_LIMIT = 20 * 1024 * 1024
MAX_PER_LISTING = 30
MAX_PIXELS = 50_000_000
# extension -> (media type, kind of file its first bytes must show, content type)
TYPES = {
	".jpg": ("Photo", "jpeg", "image/jpeg"),
	".jpeg": ("Photo", "jpeg", "image/jpeg"),
	".png": ("Photo", "png", "image/png"),
	".webp": ("Photo", "webp", "image/webp"),
	".mp4": ("Video", "mp4", "video/mp4"),
	".mov": ("Video", "mp4", "video/quicktime"),
	".webm": ("Video", "webm", "video/webm"),
}
ALLOWED = "JPG, PNG, WEBP, MP4, MOV or WEBM"


def _sniff(content: bytes) -> str:
	"""The kind of file the first bytes show, or ""."""
	if content.startswith(b"\xff\xd8\xff"):
		return "jpeg"
	if content.startswith(b"\x89PNG\r\n\x1a\n"):
		return "png"
	if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
		return "webp"
	if content[4:8] == b"ftyp":
		return "mp4"
	if content.startswith(b"\x1a\x45\xdf\xa3"):
		return "webm"
	return ""


def _check_picture(content: bytes, extension: str):
	"""A photo must open as a picture of a sensible size, not only start like one."""
	try:
		with Image.open(io.BytesIO(content)) as picture:
			picture.verify()
			width, height = picture.size
	except Exception:
		frappe.throw(
			_("The file can not be read as a {0} picture. Choose another.").format(extension[1:].upper())
		)
	if width * height > MAX_PIXELS:
		frappe.throw(_("The picture is too large. Choose one under 50 megapixels."))


def check_media(filename, content: bytes) -> tuple[str, str, str]:
	"""Refuse a file that is not a photo or a video of an allowed type and size. Returns the media type, the
	extension and the content type."""
	name = frappe.utils.cstr(filename).strip().lower()
	extension = "." + name.rsplit(".", 1)[-1] if "." in name else ""
	if extension not in TYPES:
		frappe.throw(_("A file must be a {0} file.").format(ALLOWED))
	media_type, kind, content_type = TYPES[extension]
	if not content:
		frappe.throw(_("The file is empty."))
	if _sniff(content) != kind:
		frappe.throw(
			_("The file is not a real {0} file. Choose a {1} file.").format(extension[1:].upper(), ALLOWED)
		)
	limit = PHOTO_LIMIT if media_type == "Photo" else VIDEO_LIMIT
	if len(content) > limit:
		frappe.throw(_("A {0} can be up to {1} MB.").format(media_type.lower(), limit // (1024 * 1024)))
	if media_type == "Photo":
		_check_picture(content, extension)
	return media_type, extension, content_type


def _decode(content_base64) -> bytes:
	text = str(content_base64 or "")
	if len(text) > VIDEO_LIMIT * 4 // 3 + 8:
		frappe.throw(_("A file can be up to {0} MB.").format(VIDEO_LIMIT // (1024 * 1024)))
	try:
		return base64.b64decode(text, validate=True)
	except (binascii.Error, ValueError):
		frappe.throw(_("The file could not be read. Choose it again."))


def _listing(name, write=False):
	if not name or not frappe.db.exists("Listing", name):
		frappe.throw(_("There is no listing {0}.").format(name), frappe.DoesNotExistError)
	doc = frappe.get_doc("Listing", name)
	doc.check_permission("write" if write else "read")
	if write and doc.archived:
		frappe.throw(_("An archived listing can not be changed. Restore it first."))
	return doc


def _asset_row(asset) -> dict:
	return {
		"name": asset.name,
		"title": asset.title,
		"media_type": asset.media_type,
		"file_url": asset.file,
		"file_name": asset.file_name or "",
		"content_type": asset.content_type or "",
		"size_bytes": asset.size_bytes or 0,
	}


def _state(doc) -> dict:
	assets = {
		a.name: a
		for a in frappe.get_all(
			"Media Asset",
			filters={"name": ["in", [r.media_asset for r in doc.media] or [""]]},
			fields=["name", "title", "media_type", "file", "file_name", "content_type", "size_bytes"],
		)
	}
	media = [
		{**_asset_row(assets[r.media_asset]), "position": i + 1}
		for i, r in enumerate(doc.media)
		if r.media_asset in assets
	]
	return {
		"listing": doc.name,
		"media": media,
		"can_edit": any(role in frappe.get_roles() for role in EDITORS) and not doc.archived,
		"limits": {"photo_mb": PHOTO_LIMIT // (1024 * 1024), "video_mb": VIDEO_LIMIT // (1024 * 1024)},
		"allowed": ALLOWED,
	}


def _library(doc) -> list[dict]:
	linked = {r.media_asset for r in doc.media}
	rows = frappe.get_all(
		"Media Asset",
		filters={"archived": 0},
		fields=["name", "title", "media_type", "file", "file_name", "content_type", "size_bytes"],
		order_by="creation desc",
		limit_page_length=200,
	)
	return [{**_asset_row(r), "linked": r.name in linked} for r in rows]


def _log(doc, what):
	doc.append(
		"changes",
		{
			"changed_on": frappe.utils.now_datetime(),
			"changed_by": frappe.session.user,
			"field_label": "Media",
			"old_value": "",
			"new_value": what,
		},
	)


def _store(filename, content, media_type, extension, title) -> str:
	"""Make the Media Asset, save the file as a public file with a random name attached to it, and return the
	asset's name. The file is attached when it is made, so two assets never share one file record."""
	asset = frappe.get_doc(
		{
			"doctype": "Media Asset",
			"title": title,
			"media_type": media_type,
			"file": "-",
			"file_name": squash(filename)[:140],
			"content_type": TYPES[extension][2],
			"size_bytes": len(content),
		}
	)
	asset.insert()
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"media-{secrets.token_hex(8)}{extension}",
			"content": content,
			"is_private": 0,
			"attached_to_doctype": "Media Asset",
			"attached_to_name": asset.name,
			"attached_to_field": "file",
		}
	)
	file.flags.ignore_permissions = True
	file.insert()
	asset.db_set("file", file.file_url)
	return asset.name


def _link(doc, asset):
	if len(doc.media) >= MAX_PER_LISTING:
		frappe.throw(_("A listing can have up to {0} photos and videos.").format(MAX_PER_LISTING))
	doc.append("media", {"media_asset": asset})
	_log(doc, _("Added {0}").format(frappe.db.get_value("Media Asset", asset, "title")))


def _result(doc) -> dict:
	doc.save()
	doc.reload()
	return {**_state(doc), "library": _library(doc)}


@sellos_api(*READERS)
def listing_media(listing):
	"""A listing's photos and videos in order, and the library they can be linked from."""
	doc = _listing(listing)
	return {**_state(doc), "library": _library(doc)}


@sellos_api(*EDITORS)
def upload_listing_media(listing, title, filename, content_base64):
	"""Upload a photo or a video (the file's bytes as base64) to the library and put it last on the listing."""
	doc = _listing(listing, write=True)
	title = squash(title) or squash(str(filename).rsplit(".", 1)[0])
	if not title:
		frappe.throw(_("Enter a title for the file."))
	content = _decode(content_base64)
	media_type, extension, _content_type = check_media(filename, content)
	if len(doc.media) >= MAX_PER_LISTING:
		frappe.throw(_("A listing can have up to {0} photos and videos.").format(MAX_PER_LISTING))
	_link(doc, _store(filename, content, media_type, extension, title))
	return _result(doc)


@sellos_api(*EDITORS)
def link_listing_media(listing, media_asset):
	"""Link a photo or a video from the library to the listing, last in the order. A file already on the listing
	is left where it is."""
	doc = _listing(listing, write=True)
	if not media_asset or not frappe.db.exists("Media Asset", media_asset):
		frappe.throw(_("There is no such file in the library."), frappe.DoesNotExistError)
	asset = frappe.get_doc("Media Asset", media_asset)
	asset.check_permission("read")
	if asset.archived:
		frappe.throw(_("That file is archived."))
	if any(r.media_asset == asset.name for r in doc.media):
		return {**_state(doc), "library": _library(doc)}  # already there: a second click changes nothing
	_link(doc, asset.name)
	return _result(doc)


@sellos_api(*EDITORS)
def unlink_listing_media(listing, media_asset):
	"""Take a file off the listing. It stays in the library."""
	doc = _listing(listing, write=True)
	rows = [r for r in doc.media if r.media_asset != media_asset]
	if len(rows) == len(doc.media):
		return {**_state(doc), "library": _library(doc)}  # not on it: nothing to take off
	title = frappe.db.get_value("Media Asset", media_asset, "title")
	doc.set("media", [{"media_asset": r.media_asset} for r in rows])
	_log(doc, _("Removed {0}").format(title))
	return _result(doc)


@sellos_api(*EDITORS)
def reorder_listing_media(listing, order):
	"""Set the order of the listing's files. `order` lists every one of the listing's media assets once."""
	doc = _listing(listing, write=True)
	order = frappe.parse_json(order) if isinstance(order, str) else (order or [])
	current = [r.media_asset for r in doc.media]
	if sorted(order) != sorted(current):
		frappe.throw(_("The order must list each file of the listing once."))
	if order != current:
		doc.set("media", [{"media_asset": name} for name in order])
		_log(doc, _("Order changed"))
	return _result(doc)
