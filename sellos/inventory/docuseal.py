"""Electronic signing of a mandate through DocuSeal (SOS-LOOP). Read docs/DOCUSEAL.md.

DocuSeal (https://www.docuseal.com, cloud or self hosted) emails the signers a link, collects their signatures and
keeps an audit trail. This is an electronic signature, NOT an Aadhaar eSign: counsel decides whether it is enough.

* The company's DocuSeal address and API key are settings (the key and the webhook secret are encrypted password
  fields, never in a repository and never returned by any method). With them missing, the screens say "Connect
  DocuSeal" and link to the settings.
* `send_for_signing` builds the mandate document (sellos.inventory.mandate_document), uploads it to DocuSeal as a
  template, creates a submission for the seller and the company's signer, and records the submission id and each
  signer's status and times on the mandate. The terms of the mandate are then locked until it is answered.
* DocuSeal calls the webhook (sellos.inventory.docuseal_webhook) as people view and sign. `apply_event` moves the
  statuses (Sent, Viewed, Signed, Declined, Expired) forward only, stores the signed PDF and the audit trail on the
  mandate, and moves it to Signed, which releases its Dossier.
"""

import ipaddress
import socket
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import frappe
import requests
from frappe import _
from frappe.utils import get_datetime, get_system_timezone, get_url, now_datetime

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN
from sellos.inventory import mandate_document
from sellos.inventory.base import squash
from sellos.inventory.mandates import AUDIT_FIELD, SENT_FIELD, SIGNED_FIELD, _mandate, _overview
from sellos.sellos.doctype.mandate.mandate import DRAFT, OUT_FOR_SIGNING, SIGNED

SETTINGS = "SellOS Settings"
PROVIDER = "DocuSeal"
WEBHOOK_METHOD = "sellos.inventory.docuseal_webhook.docuseal_event"
WEBHOOK_HEADER = "X-Webhook-Secret"
SETTINGS_PATH = "/company/settings"
TIMEOUT_SECONDS = 20
FILE_LIMIT = 25 * 1024 * 1024
CLOUD_HOSTS = ("api.docuseal.com", "api.docuseal.eu")
# How far along each status is. A status only ever moves to a higher one, so a late "viewed" never undoes "signed".
RANK = {"Pending": 0, "Sent": 1, "Viewed": 2, "Signed": 3, "Declined": 3, "Expired": 3}
FINAL = ("Signed", "Declined", "Expired")


class DocuSealError(Exception):
	"""DocuSeal could not be reached or refused. The message holds no key and no address."""


# --- settings -----------------------------------------------------------------------------------------


def _cfg() -> frappe._dict:
	row = frappe.get_doc(SETTINGS)
	return frappe._dict(
		url=(row.docuseal_url or "").strip(),
		key=row.get_password("docuseal_api_key", raise_exception=False) or "",
		secret=row.get_password("docuseal_webhook_secret", raise_exception=False) or "",
		signer_name=row.docuseal_signer_name or "",
		signer_email=row.docuseal_signer_email or "",
	)


def is_loopback(host: str) -> bool:
	try:
		return host == "localhost" or ipaddress.ip_address(host).is_loopback
	except ValueError:
		return False


def check_url(url: str) -> str:
	"""The address of the company's DocuSeal: https, or http to this machine only while developing or testing."""
	parts = urlparse((url or "").strip())
	if not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
		frappe.throw(_("Enter the DocuSeal address, such as https://sign.example.com."))
	dev = bool(frappe.conf.developer_mode or frappe.flags.in_test)
	if parts.scheme != "https" and not (dev and parts.scheme == "http" and is_loopback(parts.hostname)):
		frappe.throw(_("The DocuSeal address must start with https://."))
	return f"{parts.scheme}://{parts.netloc}{parts.path.rstrip('/')}"


def api_base(url: str) -> str:
	"""DocuSeal's cloud answers at its host root, a self hosted one under /api."""
	parts = urlparse(url)
	if parts.hostname in CLOUD_HOSTS or parts.path.endswith("/api"):
		return url
	return f"{url}/api"


def connected() -> bool:
	c = _cfg()
	return bool(c.url and c.key)


def request(method, path, body=None):
	"""One call to DocuSeal with the company's key. Returns its JSON answer."""
	c = _cfg()
	if not (c.url and c.key):
		raise DocuSealError("DocuSeal is not connected.")
	try:
		response = requests.request(
			method,
			f"{api_base(check_url(c.url))}{path}",
			json=body,
			headers={"X-Auth-Token": c.key, "Content-Type": "application/json"},
			timeout=TIMEOUT_SECONDS,
			allow_redirects=False,
		)
	except requests.RequestException:
		raise DocuSealError("DocuSeal could not be reached.") from None
	if not response.ok:
		raise DocuSealError(f"DocuSeal refused the request (status {response.status_code}).")
	try:
		return response.json()
	except ValueError:
		raise DocuSealError("DocuSeal answered in a way that could not be read.") from None


def _resolves_public(host) -> bool:
	try:
		addresses = {info[4][0] for info in socket.getaddrinfo(host, 443)}
	except OSError:
		return False
	return bool(addresses) and all(ipaddress.ip_address(a).is_global for a in addresses)


def fetch(url) -> bytes:
	"""Download a document DocuSeal announced. Only https (or this machine while testing), no redirect, a size cap,
	and a host that is the company's own DocuSeal or a public one: never a private address. The key goes only to the
	company's own DocuSeal."""
	c = _cfg()
	own = urlparse(c.url)
	target = urlparse(url or "")
	dev = bool(frappe.conf.developer_mode or frappe.flags.in_test)
	same = bool(target.hostname) and (target.scheme, target.netloc) == (own.scheme, own.netloc)
	if target.scheme != "https" and not (dev and same and is_loopback(target.hostname or "")):
		raise DocuSealError("A document address was not https.")
	if not same and not _resolves_public(target.hostname):
		raise DocuSealError("A document address was not a public one.")
	try:
		response = requests.get(
			url,
			headers={"X-Auth-Token": c.key} if same else {},
			timeout=TIMEOUT_SECONDS * 2,
			allow_redirects=False,
			stream=True,
		)
		if not response.ok:
			raise DocuSealError(f"A document could not be fetched (status {response.status_code}).")
		content = response.raw.read(FILE_LIMIT + 1, decode_content=True)
	except requests.RequestException:
		raise DocuSealError("A document could not be fetched.") from None
	if not content or len(content) > FILE_LIMIT or not content.startswith(b"%PDF"):
		raise DocuSealError("A document was not a PDF of a sensible size.")
	return content


# --- the settings methods -----------------------------------------------------------------------------


@sellos_api(COMPANY_ADMIN, AGENT)
def docuseal_status():
	"""Whether DocuSeal is connected (no secret), and where the settings are."""
	return {"connected": connected(), "settings_path": SETTINGS_PATH}


def _settings_view() -> dict:
	c = _cfg()
	return {
		"url": c.url,
		"signer_name": c.signer_name,
		"signer_email": c.signer_email,
		"has_api_key": bool(c.key),
		"has_webhook_secret": bool(c.secret),
		"connected": bool(c.url and c.key),
		"webhook_url": f"{get_url()}/api/method/{WEBHOOK_METHOD}",
		"webhook_header": WEBHOOK_HEADER,
	}


@sellos_api(COMPANY_ADMIN)
def get_docuseal_settings():
	"""The DocuSeal settings with no secret in them: only whether the key and the webhook secret are set."""
	return _settings_view()


@sellos_api(COMPANY_ADMIN)
def save_docuseal_settings(values):
	"""Save the DocuSeal address, the company's signer, and (when given) the API key and the webhook secret. A blank
	key or secret keeps the one saved. The key and secret are encrypted and never returned."""
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	doc = frappe.get_doc(SETTINGS)
	if "url" in values:
		doc.docuseal_url = check_url(values["url"]) if (values["url"] or "").strip() else ""
	for field in ("signer_name", "signer_email"):
		if field in values:
			value = squash(values[field])
			if field == "signer_email" and value and not frappe.utils.validate_email_address(value):
				frappe.throw(_("Enter a valid email address for the company's signer."))
			doc.set(f"docuseal_{field}", value)
	for field in ("api_key", "webhook_secret"):
		if (values.get(field) or "").strip():
			doc.set(f"docuseal_{field}", values[field].strip())
	doc.flags.ignore_permissions = True  # the caller is a Company Admin, checked by the declaration
	doc.save()
	frappe.clear_document_cache(SETTINGS, SETTINGS)
	return _settings_view()


@sellos_api(COMPANY_ADMIN)
def check_docuseal_connection():
	"""Ask DocuSeal for one template, to show the address and the key work."""
	try:
		request("GET", "/templates?limit=1")
	except DocuSealError as error:
		frappe.throw(str(error))
	return {"ok": 1}


# --- sending ------------------------------------------------------------------------------------------


def _signers(doc) -> list[dict]:
	c = _cfg()
	client = frappe.db.get_value("Lead", doc.lead, "client")
	owner = frappe.db.get_value("Client", client, ["client_name", "email"], as_dict=True) or {}
	if not (owner.get("email") or "").strip():
		frappe.throw(
			_(
				"Add the seller's email address to their client record first: DocuSeal emails them the document."
			)
		)
	if not (c.signer_name and c.signer_email):
		frappe.throw(
			_("Set the company's signer (a name and an email address) in the company settings first.")
		)
	return [
		{"role": "Seller", "name": owner.get("client_name") or doc.lead, "email": owner["email"].strip()},
		{"role": "Company", "name": c.signer_name, "email": c.signer_email},
	]


def _store(doc, field, filename, content) -> str:
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"content": content,
			"is_private": 1,
			"attached_to_doctype": "Mandate",
			"attached_to_name": doc.name,
			"attached_to_field": field,
		}
	)
	file.flags.ignore_permissions = True
	file.insert()
	return file.file_url


@sellos_api(COMPANY_ADMIN, AGENT)
def send_for_signing(name):
	"""Build the mandate document and send it through DocuSeal to the seller and the company's signer. Refused for a
	mandate that is signed, archived or already out for signing, and when DocuSeal is not connected."""
	import base64

	doc = _mandate(name, write=True)
	if doc.status != DRAFT:
		frappe.throw(_("This mandate is already signed."))
	if doc.signing_status in OUT_FOR_SIGNING:
		frappe.throw(_("This mandate is already out for signing."))
	if not connected():
		frappe.throw(_("Connect DocuSeal in the company settings first."))
	signers = _signers(doc)
	pdf, fields = mandate_document.build(mandate_document.view(doc, signers))
	try:
		template = request(
			"POST",
			"/templates/pdf",
			{
				"name": f"Mandate {doc.name}",
				"documents": [
					{
						"name": f"mandate-{doc.name}.pdf",
						"file": base64.b64encode(pdf).decode(),
						"fields": [
							{
								"name": f"{f['role']} signature",
								"type": "signature",
								"role": f["role"],
								"required": True,
								"areas": [{k: f[k] for k in ("x", "y", "w", "h", "page")}],
							}
							for f in fields
						],
					}
				],
			},
		)
		created = request(
			"POST",
			"/submissions",
			{
				"template_id": template["id"],
				"send_email": True,
				"order": "preserved",
				"submitters": [
					{"role": s["role"], "name": s["name"], "email": s["email"], "external_id": doc.name}
					for s in signers
				],
			},
		)
	except (DocuSealError, KeyError, TypeError) as error:
		frappe.throw(
			_("The mandate could not be sent for signing. {0}").format(
				error if isinstance(error, DocuSealError) else ""
			)
		)
	submitters = created if isinstance(created, list) else (created or {}).get("submitters") or []
	by_role = {s.get("role"): s for s in submitters if isinstance(s, dict)}
	submission = next(
		(s.get("submission_id") for s in submitters if isinstance(s, dict) and s.get("submission_id")), None
	)
	if not submission or set(by_role) != {"Seller", "Company"}:
		frappe.throw(_("DocuSeal answered in a way that could not be used. Nothing was sent."))
	now = now_datetime()
	doc.mandate_document = _store(doc, SENT_FIELD, f"mandate-{doc.name}.pdf", pdf)
	doc.signing_provider = PROVIDER
	doc.docuseal_submission_id = str(submission)
	doc.signing_status = "Sent"
	doc.signing_sent_on = now
	doc.signing_viewed_on = doc.signing_completed_on = doc.signing_declined_on = None
	doc.set("signers", [])
	for s in signers:
		doc.append(
			"signers",
			{
				"role": s["role"],
				"signer_name": s["name"],
				"signer_email": s["email"],
				"status": "Sent",
				"submitter_id": str(by_role[s["role"]].get("id") or ""),
				"sent_on": now,
			},
		)
	doc.save()
	return {"name": doc.name, **_overview()}


# --- DocuSeal's events --------------------------------------------------------------------------------


def _when(timestamp):
	"""DocuSeal's time (UTC) as the site's own time, or now when it is missing or unreadable."""
	try:
		moment = get_datetime(timestamp) if timestamp else None
	except (ValueError, TypeError):
		moment = None
	if not moment:
		return now_datetime()
	if moment.tzinfo:
		moment = moment.astimezone(ZoneInfo(get_system_timezone()))
	return moment.replace(tzinfo=None)


def _forward(current, new) -> bool:
	"""True when `new` is further along than `current`: a final status is never left, a late one never wins."""
	return current not in FINAL and RANK.get(new, 0) > RANK.get(current or "Pending", 0)


def _find_mandate(event_type, data):
	submission = (data.get("submission") or {}).get("id") or data.get("submission_id")
	if not submission and event_type.startswith("submission."):
		submission = data.get("id")
	return frappe.db.get_value("Mandate", {"docuseal_submission_id": str(submission)}) if submission else None


def apply_event(event_type: str, data: dict, timestamp=None) -> str:
	"""Apply one DocuSeal event to its mandate. Returns "ok" or "ignored". Statuses only move forward, so a replayed
	or out of order event changes nothing."""
	name = _find_mandate(event_type, data)
	if not name:
		return "ignored"
	doc = frappe.get_doc("Mandate", name)
	when = _when(timestamp)
	changed = False
	signer = next((s for s in doc.signers if str(s.submitter_id) == str(data.get("id"))), None)
	if event_type in ("form.viewed", "form.started") and signer:
		if _forward(signer.status, "Viewed"):
			signer.status, signer.viewed_on, changed = "Viewed", when, True
		if _forward(doc.signing_status, "Viewed"):
			doc.signing_status, changed = "Viewed", True
			doc.signing_viewed_on = doc.signing_viewed_on or when
	elif event_type == "form.completed" and signer:
		if _forward(signer.status, "Signed"):
			signer.status, signer.completed_on, changed = "Signed", when, True
		if _forward(doc.signing_status, "Viewed"):
			doc.signing_status, changed = "Viewed", True
	elif event_type == "form.declined":
		if signer and _forward(signer.status, "Declined"):
			signer.status, signer.completed_on, changed = "Declined", when, True
		if _forward(doc.signing_status, "Declined"):
			doc.signing_status, doc.signing_declined_on, changed = "Declined", when, True
	elif event_type == "submission.expired" and _forward(doc.signing_status, "Expired"):
		doc.signing_status, changed = "Expired", True
	elif event_type == "submission.completed" and _forward(doc.signing_status, "Signed"):
		_complete(doc, data, when)
		changed = True
	if not changed:
		return "ignored"
	doc.flags.ignore_permissions = (
		True  # DocuSeal is no SellOS user: the signature of the webhook was the check
	)
	doc.save()
	return "ok"


def _complete(doc, data, when):
	"""Everyone signed: keep DocuSeal's signed PDF and audit trail, and move the mandate to Signed."""
	docs = data.get("documents") or []
	url = (docs[0] or {}).get("url") if docs else None
	url = url or data.get("combined_document_url")
	pdf = fetch(url)
	audit_url = data.get("audit_log_url") or (data.get("submission") or {}).get("audit_log_url")
	audit = fetch(audit_url) if audit_url else None
	for signer in doc.signers:
		if signer.status != "Signed":
			signer.status, signer.completed_on = "Signed", when
	doc.signing_status = "Signed"
	doc.signing_completed_on = when
	if audit:
		doc.audit_trail = _store(doc, AUDIT_FIELD, f"mandate-{doc.name}-audit-trail.pdf", audit)
	if doc.status != SIGNED:
		doc.sign(_store(doc, SIGNED_FIELD, f"mandate-{doc.name}-signed.pdf", pdf))
		doc.signed_by = "Administrator"  # recorded by the signing service, not by a person at the keyboard
		doc.signed_on = when
