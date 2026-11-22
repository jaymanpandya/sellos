"""WhatsApp Settings API (SOS-P6-11): a Company Admin connects the company's own WhatsApp number.

Only a Company Admin may call these methods. The access token and the webhook signing secret are stored
encrypted (Password fields) and no method returns them, not even masked: a response says only whether each
is set. Leaving a key blank when saving keeps the saved one. Templates are the company's own list.
"""

import re

import frappe
from frappe import _

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN, SALES_MANAGER
from sellos.whatsapp.base import ProviderError
from sellos.whatsapp.provider import get_provider

DOCTYPE = "WhatsApp Settings"
TEMPLATE = "WhatsApp Template"
CATEGORIES = ("Utility", "Marketing", "Authentication")
STATUSES = ("Pending", "Approved", "Rejected")
_TEMPLATE_NAME = re.compile(r"^[a-z0-9_]{1,100}$")


def _keys() -> tuple[str, str]:
	"""(access token, signing secret), read at the moment they are used."""
	doc = frappe.get_doc(DOCTYPE)
	return doc.get_password("access_token", raise_exception=False) or "", doc.get_password(
		"app_secret", raise_exception=False
	) or ""


def connected_provider():
	"""The provider for this company's number, or a ProviderError when it is not connected."""
	token, _secret = _keys()
	number_id = frappe.db.get_single_value(DOCTYPE, "phone_number_id") or ""
	if not token or not number_id:
		raise ProviderError(_("WhatsApp is not connected. Ask your Company Admin to connect the number."))
	return get_provider(token, number_id)


def _state() -> dict:
	token, secret = _keys()
	number_id = frappe.db.get_single_value(DOCTYPE, "phone_number_id") or ""
	display = frappe.db.get_single_value(DOCTYPE, "display_number") or ""
	return {
		"access_token_set": bool(token),
		"app_secret_set": bool(secret),
		"phone_number_id": number_id,
		"display_number": display,
		"configured": bool(token and secret and number_id),
	}


@sellos_api(COMPANY_ADMIN)
def get_whatsapp_settings():
	"""What is set, never the keys themselves."""
	return _state()


@sellos_api(COMPANY_ADMIN)
def save_whatsapp_settings(access_token=None, app_secret=None, phone_number_id=None, display_number=None):
	"""Save the company's number. A blank token or secret keeps the saved one."""
	doc = frappe.get_doc(DOCTYPE)
	if (access_token or "").strip():
		doc.access_token = access_token.strip()
	if (app_secret or "").strip():
		doc.app_secret = app_secret.strip()
	if phone_number_id is not None and str(phone_number_id).strip():
		number_id = str(phone_number_id).strip()
		if not re.fullmatch(r"\d{5,25}", number_id):
			frappe.throw(_("The number ID is digits only."), frappe.ValidationError)
		doc.phone_number_id = number_id
	if display_number is not None and str(display_number).strip():
		doc.display_number = str(display_number).strip()[:30]
	doc.flags.ignore_permissions = True
	doc.save()
	return _state()


def _clean(message: str, secrets: tuple[str, ...]) -> str:
	for secret in secrets:
		if secret:
			message = message.replace(secret, "***")
	return message


@sellos_api(COMPANY_ADMIN)
def check_whatsapp_connection():
	"""Check the saved token and number with the provider. Returns {"ok", "message"}; the message is the
	success text or the provider's error, with no key in it."""
	token, secret = _keys()
	try:
		message = connected_provider().test_connection()
	except ProviderError as error:
		return {"ok": False, "message": _clean(str(error), (token, secret))}
	except Exception:
		frappe.log_error(title="WhatsApp test connection failed")
		return {"ok": False, "message": _("The connection test failed. Try again.")}
	return {"ok": True, "message": _clean(str(message), (token, secret))}


# -- templates ----------------------------------------------------------------------------------------


def _template_row(row) -> dict:
	return {
		"name": row.name,
		"language": row.language,
		"category": row.category,
		"body": row.body,
		"status": row.status,
		"enabled": int(row.enabled),
	}


@sellos_api(COMPANY_ADMIN, AGENT, SALES_MANAGER)
def list_whatsapp_templates(include_disabled=0):
	"""The company's templates. A sender sees only the enabled ones the provider approved."""
	roles = set(frappe.get_roles())
	filters = {} if int(include_disabled or 0) and COMPANY_ADMIN in roles else {"enabled": 1}
	if COMPANY_ADMIN not in roles:
		filters["status"] = "Approved"
	rows = frappe.get_all(
		TEMPLATE,
		filters=filters,
		fields=["name", "language", "category", "body", "status", "enabled"],
		order_by="creation asc",
	)
	return [_template_row(row) for row in rows]


@sellos_api(COMPANY_ADMIN)
def save_whatsapp_template(name, body, language="en", category="Utility", status="Pending", enabled=1):
	"""Add a template or change one. A template is never deleted: switch it off with enabled 0."""
	name = (name or "").strip()
	if not _TEMPLATE_NAME.match(name):
		frappe.throw(
			_("A template name is lower case letters, digits and underscores."), frappe.ValidationError
		)
	if category not in CATEGORIES or status not in STATUSES:
		frappe.throw(_("Choose a valid category and approval status."), frappe.ValidationError)
	if not (body or "").strip():
		frappe.throw(_("A template needs its message."), frappe.ValidationError)
	values = {
		"body": body.strip(),
		"language": (language or "en").strip(),
		"category": category,
		"status": status,
		"enabled": 1 if int(enabled) else 0,
	}
	if frappe.db.exists(TEMPLATE, name):
		doc = frappe.get_doc(TEMPLATE, name)
		doc.update(values)
	else:
		doc = frappe.get_doc({"doctype": TEMPLATE, "template_name": name, **values})
	doc.flags.ignore_permissions = True
	doc.save()
	return _template_row(doc)
