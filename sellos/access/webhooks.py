"""Provider webhooks (SOS-P2-06): the one kind of method that may be called without a login.

A provider such as Plivo (calls, P2), WhatsApp or email (P5) or a payment provider (P6) calls SellOS
with no SellOS user. Such a method is registered here with `provider_webhook`, never with
`@sellos_api`, and it is the only method in the sellos package that allows guests
(`sellos/access/test_webhook_guest_guard.py` fails the build otherwise). The rules are in CLAUDE.md
("Provider webhooks") and docs/permissions.md. This module runs every shared check once, so a new
provider only supplies its own signature function and its own handler:

1. The body is capped. A request that says it is larger is refused before anything else.
2. Requests are limited per tenant (a minute window kept in the cache, never the database).
3. The signature is checked against the tenant's secret before any write. Every failure (no secret, no
   signature, a bad one, an unreadable request) gets the same short answer and writes nothing.
4. A replayed event (its key is already remembered) changes nothing. The key is remembered per tenant
   in Webhook Event. The handler decides what an out of order event is and ignores it.

The tenant is the site the request arrives on (every company is its own site), so nothing in the body,
a header or the query can choose it. The signing secret is read from a password field of the tenant's
settings and is never logged, returned or put in an error.
"""

import functools
import hashlib
import time
from dataclasses import dataclass

import frappe

REFUSED_STATUS = 403
TOO_LARGE_STATUS = 413
RATE_LIMITED_STATUS = 429
# One short answer for every refusal of a signature, so a caller learns nothing from it.
REFUSED_ANSWER = "refused"
RATE_WINDOW_SECONDS = 60

# dotted method path -> the checks it declares
_WEBHOOKS: dict[str, dict] = {}

# Modules that register webhooks. A fresh server process imports none of them when its first request
# arrives, so the request guard imports them to know the method is a registered webhook.
WEBHOOK_MODULES = ("sellos.telephony.webhook",)


def declared_webhooks() -> dict[str, dict]:
	"""Every registered webhook and the checks it declares."""
	return {path: dict(checks) for path, checks in _WEBHOOKS.items()}


def load_webhook_modules():
	import importlib

	for module in WEBHOOK_MODULES:
		importlib.import_module(module)


def is_webhook(method_path: str | None) -> bool:
	if not method_path or not method_path.startswith("sellos."):
		return False
	load_webhook_modules()
	return method_path in _WEBHOOKS


@dataclass
class WebhookRequest:
	"""What a handler gets: the request as received, after every shared check has passed."""

	body: bytes
	headers: dict  # header names in lower case
	url: str  # the address the provider called, as it signs it
	params: dict  # the form fields
	event_key: str  # the verified replay key (a nonce or an event id)
	# There is no tenant field: the tenant is the site the request arrives on (frappe.local.site).


def _split_setting(setting: str) -> tuple[str, str]:
	doctype, _sep, fieldname = setting.rpartition(".")
	if not doctype or not fieldname:
		raise ValueError("secret_setting must be 'DocType.fieldname'")
	return doctype, fieldname


def read_secret(setting: str) -> str:
	"""The tenant's signing secret from a password field of its settings, or an empty string."""
	doctype, fieldname = _split_setting(setting)
	return frappe.get_doc(doctype).get_password(fieldname, raise_exception=False) or ""


def _request_url(request) -> str:
	query = request.query_string.decode("utf-8", "replace")
	return f"https://{request.host}{request.path}" + (f"?{query}" if query else "")


def _answer(status_code: int, answer: str):
	frappe.local.response["http_status_code"] = status_code
	return answer


def over_rate_limit(path: str, limit: int, now: float | None = None) -> bool:
	"""Count this request in the tenant's current minute. True when it is over the limit.

	frappe.cache keys carry the site's database name, so the count is per tenant."""
	window = int((now if now is not None else time.time()) // RATE_WINDOW_SECONDS)
	key = frappe.cache.make_key(f"sellos_webhook_rate:{path}:{window}")
	count = frappe.cache.incrby(key, 1)
	if count == 1:
		frappe.cache.expire(key, RATE_WINDOW_SECONDS * 2)
	return count > limit


def remember_event(provider: str, event_key: str) -> bool:
	"""Remember an event key for this tenant. False when it was already remembered (a replay)."""
	digest = hashlib.sha256(f"{provider}:{event_key}".encode()).hexdigest()
	try:
		frappe.get_doc({"doctype": "Webhook Event", "provider": provider, "event_key": digest}).insert(
			ignore_permissions=True
		)
	except frappe.UniqueValidationError:
		return False
	return True


def provider_webhook(*, provider, signature, replay, max_body_bytes, rate_limit_per_tenant, secret_setting):
	"""Register the decorated function as a provider webhook and whitelist it for guests.

	provider: the provider's short name, the scope of its replay keys.
	signature: `verify(request, secret) -> event_key or None`, given the raw body, headers, url and
	  form of the request. It returns the key that identifies this event (a nonce or an event id) only
	  when the signature is valid, and None otherwise. It runs before any write.
	replay: a sentence saying how a replayed and an out of order event are ignored.
	max_body_bytes, rate_limit_per_tenant: the body cap and the requests per minute per tenant.
	secret_setting: "DocType.fieldname" of the password field that holds the tenant's signing secret.

	The decorated function takes the WebhookRequest and returns a short result. It is called only for a
	request that passed every check and is not a replay."""
	_split_setting(secret_setting)
	if max_body_bytes < 1 or rate_limit_per_tenant < 1 or not callable(signature) or not replay:
		raise ValueError("a webhook declares a signature check, replay rule, body cap and rate limit")

	def decorate(handler):
		path = f"{handler.__module__}.{handler.__name__}"
		_WEBHOOKS[path] = {
			"provider": provider,
			"signature": signature.__name__,
			"replay": replay,
			"max_body_bytes": max_body_bytes,
			"rate_limit_per_tenant": rate_limit_per_tenant,
			"secret_setting": secret_setting,
		}

		@functools.wraps(handler)
		def endpoint():
			request = frappe.local.request
			# 1. The cap, from what the request says, before anything is read or looked up.
			length = request.content_length
			if length is not None and length > max_body_bytes:
				return _answer(TOO_LARGE_STATUS, "too large")
			# 2. The rate limit, in the cache: a flood of unsigned requests writes nothing.
			if over_rate_limit(path, rate_limit_per_tenant):
				return _answer(RATE_LIMITED_STATUS, "rate limited")
			body = request.get_data(cache=True)
			if len(body) > max_body_bytes:
				return _answer(TOO_LARGE_STATUS, "too large")
			# 3. The signature, with no write. Every failure is the same answer.
			secret = read_secret(secret_setting)
			if not secret:
				return _answer(REFUSED_STATUS, REFUSED_ANSWER)
			webhook_request = WebhookRequest(
				body=body,
				headers={key.lower(): value for key, value in request.headers.items()},
				url=_request_url(request),
				params=request.form.to_dict(),
				event_key="",
			)
			try:
				event_key = signature(webhook_request, secret)
			except Exception:
				event_key = None
			if not event_key:
				return _answer(REFUSED_STATUS, REFUSED_ANSWER)
			webhook_request.event_key = str(event_key)
			# 4. A replay changes nothing.
			if not remember_event(provider, webhook_request.event_key):
				return "ignored"
			return handler(webhook_request)

		return frappe.whitelist(allow_guest=True, methods=["POST"])(endpoint)

	return decorate
