"""The Integrations screen's methods (SOS-INT-1): a Company Admin enters the company's own provider keys.

Each company is its own site and database, so these keys are that company's alone: no method takes a company or
a site, and none can reach another database. Only a Company Admin may call any method here.

* The keys stay where their consumers read them. WhatsApp's are in WhatsApp Settings, DocuSeal's in SellOS Settings
  (where Company settings kept them before, so nothing is copied), and Meta Lead Ads, email and LegiScore in
  Integration Settings. Plivo and voice stay in Telephony Settings (SOS-P2-01): the screen only links to it.
* Every secret is a Password field, encrypted. A response never holds one: it holds "Saved, ending xxxx" (the last
  four characters) or nothing. A blank secret on save keeps the saved one, so replacing is allowed and reading is not.
* Test connection runs the provider's read only check (`sellos.config.integration_checks`) and records the plain
  reason when it fails. The record holds no secret, and a result counts only for the values it was run with.
"""

import hashlib
import hmac
import json
import re

import frappe
from frappe import _
from frappe.utils import get_url, now_datetime
from frappe.utils.password import get_encryption_key

from sellos.access.registry import sellos_api
from sellos.access.roles import COMPANY_ADMIN
from sellos.config import integration_checks
from sellos.config.integration_checks import CheckFailed

STORE = "Integration Settings"
SETTINGS = "SellOS Settings"
WHATSAPP = "WhatsApp Settings"
MAX_LENGTH = 1000
TELEPHONY_PATH = "/company/telephony"

NOT_SET, NOT_TESTED, CONNECTED, FAILED = "Not set", "Not tested", "Connected", "Failed"


def _f(key, label, field, doctype, secret=False, kind="text", hint=""):
	return {
		"key": key,
		"label": label,
		"fieldname": field,
		"doctype": doctype,
		"secret": secret,
		"kind": kind,
		"hint": hint,
	}


# provider -> its card: the title, what it is for, the fields (in the order shown) and the fields that must be set
# before it counts as set.
PROVIDERS = {
	"whatsapp": {
		"title": "WhatsApp (Meta Cloud API)",
		"help": "Your own WhatsApp Business number, used by the WhatsApp inbox and its automatic replies.",
		"required": ("access_token", "phone_number_id"),
		"fields": [
			_f("access_token", "Access token", "access_token", WHATSAPP, secret=True),
			_f("phone_number_id", "Phone number ID", "phone_number_id", WHATSAPP, kind="digits"),
			_f("waba_id", "WhatsApp business account ID", "waba_id", WHATSAPP, kind="digits"),
			_f("app_secret", "App secret", "app_secret", WHATSAPP, secret=True),
			_f("verify_token", "Webhook verify token", "verify_token", WHATSAPP, secret=True),
		],
	},
	"meta_lead_ads": {
		"title": "Meta Lead Ads",
		"help": "Brings the leads of your Facebook and Instagram lead forms into SellOS.",
		"required": ("page_access_token", "page_id"),
		"fields": [
			_f("app_id", "App ID", "meta_app_id", STORE, kind="digits"),
			_f("app_secret", "App secret", "meta_app_secret", STORE, secret=True),
			_f("page_access_token", "Page access token", "meta_page_access_token", STORE, secret=True),
			_f("page_id", "Page ID", "meta_page_id", STORE, kind="digits"),
		],
	},
	"email": {
		"title": "Email",
		"help": "The address SellOS sends your company's email from: an SMTP account, or a provider API key.",
		"required": (),  # from address, and a host or an API key: see _configured
		"fields": [
			_f("host", "SMTP host", "email_host", STORE, kind="host"),
			_f("port", "SMTP port", "email_port", STORE, kind="port"),
			_f("user", "SMTP user", "email_user", STORE),
			_f("password", "SMTP password", "email_password", STORE, secret=True),
			_f("from_name", "From name", "email_from_name", STORE),
			_f("from_address", "From address", "email_from_address", STORE, kind="email"),
			_f("api_key", "Provider API key", "email_api_key", STORE, secret=True),
		],
	},
	"docuseal": {
		"title": "DocuSeal",
		"help": "Electronic signing of mandates. It is an electronic signature, not an Aadhaar eSign: your counsel decides whether it is enough.",
		"required": ("url", "api_key"),
		"fields": [
			_f("url", "DocuSeal address", "docuseal_url", SETTINGS, kind="url"),
			_f("api_key", "API key", "docuseal_api_key", SETTINGS, secret=True),
			_f("webhook_secret", "Webhook secret", "docuseal_webhook_secret", SETTINGS, secret=True),
			_f("signer_name", "Company signer name", "docuseal_signer_name", SETTINGS),
			_f("signer_email", "Company signer email", "docuseal_signer_email", SETTINGS, kind="email"),
		],
	},
	"legiscore": {
		"title": "LegiScore",
		"help": "Only for a company that brings its own LegiScore account. Without one, the platform's own key is used.",
		"required": ("api_key",),
		"fields": [_f("api_key", "API key", "legiscore_api_key", STORE, secret=True)],
	},
}


def _spec(provider) -> dict:
	spec = PROVIDERS.get(provider)
	if not spec:
		frappe.throw(_("Choose one of the integrations on the screen."), frappe.ValidationError)
	return spec


def _doc(doctype):
	return frappe.get_doc(doctype)


def _read(spec) -> dict:
	"""Every field of a provider, secrets decrypted. For use inside this module only: never returned."""
	docs = {}
	values = {}
	for field in spec["fields"]:
		doc = docs.setdefault(field["doctype"], _doc(field["doctype"]))
		if field["secret"]:
			values[field["key"]] = doc.get_password(field["fieldname"], raise_exception=False) or ""
		else:
			value = doc.get(field["fieldname"])
			values[field["key"]] = "" if value in (None, 0) else str(value)  # an empty Int field reads 0
	return values


def mask(secret: str) -> str:
	"""What the browser may learn of a saved secret: its last four characters, and only when it is long enough
	for that to give nothing away."""
	if not secret:
		return ""
	return f"Saved, ending {secret[-4:]}" if len(secret) >= 12 else "Saved"


def _configured(provider, values) -> bool:
	if provider == "email":
		return bool(values["from_address"] and (values["host"] or values["api_key"]))
	return all(values[key] for key in PROVIDERS[provider]["required"])


def _fingerprint(values) -> str:
	"""A keyed hash of a provider's values, so a recorded test result is ignored once any of them changes."""
	body = json.dumps(values, sort_keys=True).encode()
	return hmac.new(get_encryption_key().encode(), body, hashlib.sha256).hexdigest()


def _results() -> dict:
	raw = frappe.db.get_single_value(STORE, "check_results") or "{}"
	try:
		data = json.loads(raw)
	except ValueError:
		return {}
	return data if isinstance(data, dict) else {}


def _record(provider, values, ok, reason):
	results = _results()
	results[provider] = {
		"ok": bool(ok),
		"reason": reason,
		"at": str(now_datetime()),
		"fingerprint": _fingerprint(values),
	}
	frappe.db.set_single_value(STORE, "check_results", json.dumps(results))


def _status(provider, values) -> tuple[str, str]:
	if not _configured(provider, values):
		return NOT_SET, ""
	result = _results().get(provider)
	if not result or not hmac.compare_digest(result.get("fingerprint", ""), _fingerprint(values)):
		return NOT_TESTED, ""
	return (CONNECTED, "") if result.get("ok") else (FAILED, result.get("reason") or "")


def _extras(provider) -> dict:
	if provider == "whatsapp":
		return {"webhook_url": f"{get_url()}/api/method/sellos.whatsapp.webhook.whatsapp_event"}
	if provider == "docuseal":
		return {
			"webhook_url": f"{get_url()}/api/method/sellos.inventory.docuseal_webhook.docuseal_event",
			"webhook_header": "X-Webhook-Secret",
		}
	return {}


def _card(provider) -> dict:
	spec = PROVIDERS[provider]
	values = _read(spec)
	status, reason = _status(provider, values)
	fields = []
	for field in spec["fields"]:
		value = values[field["key"]]
		shown = {
			"key": field["key"],
			"label": field["label"],
			"secret": field["secret"],
			"kind": field["kind"],
		}
		if field["secret"]:
			shown.update(value="", saved=mask(value))  # the value is never sent, only the last four
		else:
			shown.update(value=value, saved="")
		fields.append(shown)
	return {
		"provider": provider,
		"title": spec["title"],
		"help": spec["help"],
		"status": status,
		"reason": reason,
		"fields": fields,
		**_extras(provider),
	}


@sellos_api(COMPANY_ADMIN)
def list_integrations():
	"""Every card with its fields and status. A secret shows only "Saved, ending xxxx"."""
	telephony = frappe.db.get_single_value("Telephony Settings", "phone_number")
	return {
		"providers": [_card(provider) for provider in PROVIDERS],
		"voice": {"title": "Plivo and voice", "path": TELEPHONY_PATH, "configured": bool(telephony)},
	}


def _clean_value(field, value) -> str:
	value = "" if value is None else str(value).strip()
	if len(value) > MAX_LENGTH:
		frappe.throw(_("{0} is too long.").format(field["label"]), frappe.ValidationError)
	if not value:
		return ""
	kind = field["kind"]
	if kind == "digits" and not re.fullmatch(r"\d{3,40}", value):
		frappe.throw(_("{0} is digits only.").format(field["label"]), frappe.ValidationError)
	if kind == "port" and not (value.isdigit() and 1 <= int(value) <= 65535):
		frappe.throw(_("The SMTP port is a number from 1 to 65535."), frappe.ValidationError)
	if kind == "email" and not frappe.utils.validate_email_address(value):
		frappe.throw(_("{0} is not a valid email address.").format(field["label"]), frappe.ValidationError)
	if kind == "host" and not re.fullmatch(r"[A-Za-z0-9.\-]{1,253}", value):
		frappe.throw(_("The SMTP host is a name such as smtp.example.com."), frappe.ValidationError)
	if kind == "url":
		from sellos.inventory.docuseal import check_url

		value = check_url(value)
	return value


@sellos_api(COMPANY_ADMIN)
def save_integration(provider, values=None):
	"""Save one card. A blank secret keeps the saved one; a blank plain field clears it. An unknown field is refused."""
	spec = _spec(provider)
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	if not isinstance(values, dict):
		frappe.throw(_("The values could not be read."), frappe.ValidationError)
	fields = {field["key"]: field for field in spec["fields"]}
	if set(values) - set(fields):
		frappe.throw(_("One of the fields is not part of this integration."), frappe.ValidationError)
	docs = {}
	for key, raw in values.items():
		field = fields[key]
		value = _clean_value(field, raw)
		if field["secret"] and not value:
			continue
		doc = docs.setdefault(field["doctype"], _doc(field["doctype"]))
		doc.set(field["fieldname"], value or None)
	for doc in docs.values():
		doc.flags.ignore_permissions = True  # the caller is a Company Admin, checked by the declaration
		doc.save()
		frappe.clear_document_cache(doc.doctype, doc.name)
	return _card(provider)


@sellos_api(COMPANY_ADMIN)
def check_integration(provider):
	"""Run the provider's read only check with the saved values. Returns {"ok", "message", "card"}; the message is
	the success text or the provider's plain reason, with no key in it."""
	spec = _spec(provider)
	values = _read(spec)
	if not _configured(provider, values):
		return {"ok": False, "message": _("Enter and save the details first."), "card": _card(provider)}
	secrets = tuple(v for field in spec["fields"] if field["secret"] for v in (values[field["key"]],))
	try:
		message = integration_checks.run(provider, values)
		ok = True
	except CheckFailed as error:
		message, ok = _scrub(str(error), secrets), False
	except Exception:
		message, ok = _("The connection test failed. Try again."), False
	_record(provider, values, ok, "" if ok else message)
	return {"ok": ok, "message": message, "card": _card(provider)}


def _scrub(message: str, secrets) -> str:
	for secret in secrets:
		if secret:
			message = message.replace(secret, "***")
	return message[:300]
