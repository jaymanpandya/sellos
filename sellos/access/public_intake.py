"""Public intake forms (SOS-P2-08): the second kind of method that may be called without a login.

The submit method of a public form (the enquiry page, SOS-P2-08; the website form, SOS-P1-09) is
registered here with `public_intake`, never with `@sellos_api`, and allows guests
(`sellos/access/test_webhook_guest_guard.py` fails the build otherwise). It may only create or merge a
lead through `sellos.crm.intake`. The rules are in CLAUDE.md ("Public intake forms") and
docs/permissions.md. This module runs every shared check once, in this order, so a new form supplies
only its fields and its handler:

1. The body is capped: a request that says it is larger is refused before it is read.
2. Requests are limited per address and per tenant (a minute window in the cache, never the database).
3. A filled honeypot field gets the same thank you and a reference code, and nothing is written.
4. The tenant's form key is checked before any write. A bad key and any invalid field get the same
   short answer, which says nothing about why.
5. The fields are validated strictly: known fields only, each of the declared type and length.
6. The handler runs. The answer is only {"thank_you", "reference"}: nothing about whether the person
   existed, which lead was merged or what was written.

The tenant is the site the request arrives on, so no field, header or query can choose it. The method
sets no cookie and returns no record data. The form key is a password field of the tenant's settings,
which a Company Admin rotates, and it is never logged or returned except to that Company Admin.
"""

import functools
import hashlib
import hmac
import re
import time
from dataclasses import dataclass

import frappe
from frappe import _

from sellos.access import intake_keys
from sellos.access.webhooks import RATE_WINDOW_SECONDS, TOO_LARGE_STATUS, over_rate_limit

RATE_LIMITED_STATUS = 429
BAD_FORM_STATUS = 400
THANK_YOU = "Thank you. We will be in touch."
BAD_FORM_ANSWER = "We could not take this form. Please check it and try again."
FORM_KEY_SETTING = "SellOS Settings.enquiry_form_key"
FORM_KEY_FIELD = "key"
REFERENCE_LENGTH = 8

_INTAKES: dict[str, dict] = {}

# Modules that register public intake methods (a fresh server process imports none of them when its first
# request arrives, so the request guard imports them to know the method is registered).
INTAKE_MODULES = ("sellos.crm.enquiry", "sellos.crm.website_form")


@dataclass
class Field:
	"""One declared field: its type ("text" or "flag"), its longest length and whether it is needed."""

	kind: str = "text"
	max_length: int = 140
	required: bool = False
	pattern: str = ""


@dataclass
class IntakeRequest:
	"""What a handler gets, after every shared check has passed. There is no tenant field."""

	fields: dict  # the validated fields, every declared field present ("" or False when not sent)
	address: str  # the caller's address, for the consent evidence
	reference: str  # the reference code the person is given; the handler names its evidence with it


def declared_intakes() -> dict[str, dict]:
	"""Every registered public intake method and the checks it declares."""
	return {path: dict(checks) for path, checks in _INTAKES.items()}


def load_intake_modules():
	import importlib

	for module in INTAKE_MODULES:
		importlib.import_module(module)


def is_public_intake(method_path: str | None) -> bool:
	if not method_path or not method_path.startswith("sellos."):
		return False
	load_intake_modules()
	return method_path in _INTAKES


# --- the form key (a Company Admin rotates it) ---------------------------------------------------------


def _split_setting() -> tuple[str, str]:
	doctype, _sep, fieldname = FORM_KEY_SETTING.rpartition(".")
	return doctype, fieldname


def _read_key() -> str:
	doctype, fieldname = _split_setting()
	return frappe.get_doc(doctype).get_password(fieldname, raise_exception=False) or ""


def form_key() -> str:
	"""The tenant's form key. The first call makes one."""
	return _read_key() or rotate_form_key()


def rotate_form_key() -> str:
	"""Make a new form key. Every link that carries the old one stops working."""
	doctype, fieldname = _split_setting()
	key = frappe.generate_hash(length=24)
	doc = frappe.get_doc(doctype)
	doc.set(fieldname, key)
	doc.flags.ignore_permissions = True
	doc.save()
	return key


def key_matches(given) -> bool:
	key = _read_key()
	return bool(key) and isinstance(given, str) and hmac.compare_digest(key.encode(), given.encode())


# --- the shared checks -----------------------------------------------------------------------------------


def _answer(status_code: int, answer: str):
	frappe.local.response["http_status_code"] = status_code
	return answer


def over_address_limit(path: str, address: str, limit: int, now: float | None = None) -> bool:
	"""Count this request for this address in the current minute (per tenant: the cache key carries the
	site). True when it is over the limit."""
	window = int((now if now is not None else time.time()) // RATE_WINDOW_SECONDS)
	digest = hashlib.sha256(address.encode()).hexdigest()[:24]
	key = frappe.cache.make_key(f"sellos_intake_rate:{path}:{digest}:{window}")
	count = frappe.cache.incrby(key, 1)
	if count == 1:
		frappe.cache.expire(key, RATE_WINDOW_SECONDS * 2)
	return count > limit


def validate_fields(raw: dict, spec: dict[str, Field], honeypot: str) -> dict | None:
	"""The clean fields, or None when anything is wrong: an unknown field, a wrong type, too long, missing."""
	if set(raw) - (set(spec) | {honeypot, FORM_KEY_FIELD}):
		return None
	clean = {}
	for name, rule in spec.items():
		value = raw.get(name)
		if rule.kind == "flag":
			if value in (None, "", 0, "0", False, "false"):
				clean[name] = False
			elif value in (1, "1", True, "true", "on"):
				clean[name] = True
			else:
				return None
			continue
		if value is None:
			value = ""
		if not isinstance(value, str):
			return None
		value = value.strip()
		if len(value) > rule.max_length or (rule.required and not value):
			return None
		if value and rule.pattern and not re.fullmatch(rule.pattern, value):
			return None
		clean[name] = value
	return clean


def public_intake(
	*,
	fields: dict[str, Field],
	honeypot_field,
	max_body_bytes,
	rate_limit_per_address,
	rate_limit_per_tenant,
	consent_evidence,
	calls_intake,
	key_scope=None,
):
	"""Register the decorated function as a public intake method and whitelist it for guests.

	fields: every field the form may send, as `Field`. Anything else is refused.
	honeypot_field: the name of the field a person never fills. A filled one is thanked and ignored.
	max_body_bytes, rate_limit_per_address, rate_limit_per_tenant: the body cap and the requests per
	  minute for one address and for the whole tenant.
	consent_evidence: a sentence saying what is saved as the Consent Record's evidence file.
	calls_intake: the dotted path of the `sellos.crm.intake` function the handler uses.
	key_scope: set it (an `sellos.access.intake_keys` scope) when the form is opened by a per company key
	  record of that scope (SOS-P1-09) instead of the tenant's form key setting.

	The decorated function takes an IntakeRequest. It is called only for a request that passed every
	check, and it makes or merges the lead through the intake function."""
	if (
		not fields
		or not honeypot_field
		or min(max_body_bytes, rate_limit_per_address, rate_limit_per_tenant) < 1
		or not consent_evidence
		or not str(calls_intake).startswith("sellos.crm.intake.")
	):
		raise ValueError("a public intake declares its fields, honeypot, caps, evidence and intake call")

	def decorate(handler):
		path = f"{handler.__module__}.{handler.__name__}"
		_INTAKES[path] = {
			"write_only": "Answers a thank you and a reference code only.",
			"rate_limit_per_address": rate_limit_per_address,
			"rate_limit_per_tenant": rate_limit_per_tenant,
			"honeypot_field": honeypot_field,
			"max_body_bytes": max_body_bytes,
			"field_validation": sorted(fields),
			"form_key_setting": f"Intake Key ({key_scope})" if key_scope else FORM_KEY_SETTING,
			"consent_evidence": consent_evidence,
			"calls_intake": calls_intake,
		}

		@functools.wraps(handler)
		def endpoint():
			request = frappe.local.request
			# 1. The cap, from what the request says, before anything is read.
			length = request.content_length
			if length is not None and length > max_body_bytes:
				return _answer(TOO_LARGE_STATUS, "too large")
			# 2. The limits, in the cache: a flood writes nothing.
			address = str(frappe.local.request_ip or "")
			if over_rate_limit(path, rate_limit_per_tenant) or over_address_limit(
				path, address, rate_limit_per_address
			):
				return _answer(RATE_LIMITED_STATUS, "rate limited")
			if len(request.get_data(cache=True)) > max_body_bytes:
				return _answer(TOO_LARGE_STATUS, "too large")
			raw = {key: value for key, value in frappe.form_dict.items() if key != "cmd"}
			reference = frappe.generate_hash(length=REFERENCE_LENGTH).upper()
			thanks = {"thank_you": _(THANK_YOU), "reference": reference}
			# 3. The honeypot: the same thank you, and nothing is written.
			if raw.get(honeypot_field):
				return thanks
			# 4. The form key, before any write. Every failure is the same short answer.
			given = raw.get(FORM_KEY_FIELD)
			if not (intake_keys.key_valid(given, key_scope) if key_scope else key_matches(given)):
				return _answer(BAD_FORM_STATUS, _(BAD_FORM_ANSWER))
			# 5. Strict validation.
			clean = validate_fields(raw, fields, honeypot_field)
			if clean is None:
				return _answer(BAD_FORM_STATUS, _(BAD_FORM_ANSWER))
			try:
				handler(IntakeRequest(fields=clean, address=address, reference=reference))
			except frappe.ValidationError:  # a field the intake function could not use, such as a phone
				frappe.db.rollback()
				return _answer(BAD_FORM_STATUS, _(BAD_FORM_ANSWER))
			except Exception:
				frappe.db.rollback()
				frappe.log_error(title="Public intake failed")
				return _answer(BAD_FORM_STATUS, _(BAD_FORM_ANSWER))
			return thanks

		return frappe.whitelist(allow_guest=True, methods=["POST"])(endpoint)

	return decorate
