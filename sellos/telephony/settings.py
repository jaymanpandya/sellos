"""Telephony Settings API (SOS-P2-01): a Company Admin enters the Plivo India account once.

Only a Company Admin may call these methods. The auth ID and the auth token are stored encrypted
(Password fields) and no method returns them, not even masked: a response says only whether each is
set. Leaving a key blank when saving keeps the saved one. International calling is dropped, so there
is one account.
"""

import re

import frappe
from frappe import _

from sellos.access.registry import sellos_api
from sellos.access.roles import COMPANY_ADMIN
from sellos.telephony.provider import ProviderError, get_provider

DOCTYPE = "Telephony Settings"
# A Mumbai landline: the 022 area code and eight digits, with or without the country code.
_LANDLINE = re.compile(r"^(?:\+?91)?0?22(\d{8})$")


def normalise_landline(value: str) -> str:
	"""The 022 number as +9122 and eight digits, or a validation error."""
	match = _LANDLINE.match(re.sub(r"[\s\-()]", "", value or ""))
	if not match:
		frappe.throw(_("Enter the 022 number with its area code and eight digits."), frappe.ValidationError)
	return f"+9122{match.group(1)}"


def _keys() -> tuple[str, str]:
	doc = frappe.get_doc(DOCTYPE)
	return doc.get_password("auth_id", raise_exception=False) or "", doc.get_password(
		"auth_token", raise_exception=False
	) or ""


def _state() -> dict:
	auth_id, auth_token = _keys()
	number = frappe.db.get_single_value(DOCTYPE, "phone_number") or ""
	return {
		"auth_id_set": bool(auth_id),
		"auth_token_set": bool(auth_token),
		"phone_number": number,
		"configured": bool(auth_id and auth_token and number),
	}


@sellos_api(COMPANY_ADMIN)
def get_telephony_settings():
	"""What is set, never the keys themselves."""
	return _state()


@sellos_api(COMPANY_ADMIN)
def save_telephony_settings(auth_id=None, auth_token=None, phone_number=None):
	"""Save the account. A blank auth ID or auth token keeps the saved one."""
	auth_id = (auth_id or "").strip()
	auth_token = (auth_token or "").strip()
	doc = frappe.get_doc(DOCTYPE)
	if phone_number is not None and str(phone_number).strip():
		doc.phone_number = normalise_landline(str(phone_number))
	if auth_id:
		doc.auth_id = auth_id
	if auth_token:
		doc.auth_token = auth_token
	doc.flags.ignore_permissions = True
	doc.save()
	return _state()


def _clean(message: str, secrets: tuple[str, ...]) -> str:
	for secret in secrets:
		if secret:
			message = message.replace(secret, "***")
	return message


@sellos_api(COMPANY_ADMIN)
def check_connection():
	"""Check the saved keys with the provider. Returns {"ok", "message"}; the message is the success
	text or the provider's error, with no key in it."""
	auth_id, auth_token = _keys()
	if not auth_id or not auth_token:
		return {"ok": False, "message": _("Save the auth ID and the auth token first.")}
	try:
		message = get_provider(auth_id, auth_token).test_connection()
	except ProviderError as error:
		return {"ok": False, "message": _clean(str(error), (auth_id, auth_token))}
	except Exception:
		frappe.log_error(title="Telephony test connection failed")
		return {"ok": False, "message": _("The connection test failed. Try again.")}
	return {"ok": True, "message": _clean(str(message), (auth_id, auth_token))}
