"""The outbound listings change webhook (SOS-P4-08).

When a published listing changes, SellOS tells the company's website, so it can fetch the feed again. The
call carries ids and the kind of change only: no name, phone, price or any other record data. It is:

* signed with the tenant's own secret (a password field of the settings, never logged or returned except
  once to the Company Admin who makes it): `X-SellOS-Signature: sha256=<HMAC of "<timestamp>.<body>">`,
  with the timestamp in `X-SellOS-Timestamp`;
* sent over HTTPS only, to an address whose host resolves only to public addresses (a private, loopback or
  link local address is refused), and never follows a redirect;
* retried, with a pause between tries, and then logged without the address or the secret.
"""

import hashlib
import hmac
import ipaddress
import json
import socket
import time
from urllib.parse import urlsplit

import frappe
import requests
from frappe import _

SETTINGS = "SellOS Settings"
URL_FIELD = "listings_webhook_url"
SECRET_FIELD = "listings_webhook_secret"
EVENT = "listing.changed"
PUBLISHED, UPDATED, UNPUBLISHED = "published", "updated", "unpublished"
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (2, 10)
TIMEOUT_SECONDS = 10
# What a change to a published listing means to the website.
WATCHED = ("title", "listing_type", "unit", "property", "asking_price", "description")


def _sleep(seconds):
	time.sleep(seconds)


def _post(url, body: bytes, headers: dict) -> int:
	response = requests.post(url, data=body, headers=headers, timeout=TIMEOUT_SECONDS, allow_redirects=False)
	return response.status_code


def _resolve(host: str) -> list[str]:
	return sorted({info[4][0] for info in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)})


def check_url(url: str) -> str:
	"""The host of a webhook address, or a refusal: HTTPS only, a host name or public address, no login
	in the address. Resolving the host is done at send time (`check_public`)."""
	parts = urlsplit((url or "").strip())
	if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
		frappe.throw(_("The change webhook address must be an https:// address."), frappe.ValidationError)
	if parts.hostname.lower() in ("localhost",) or parts.hostname.lower().endswith(".localhost"):
		frappe.throw(_("The change webhook address must be a public address."), frappe.ValidationError)
	try:
		literal = ipaddress.ip_address(parts.hostname)
	except ValueError:
		return parts.hostname
	if not literal.is_global:
		frappe.throw(_("The change webhook address must be a public address."), frappe.ValidationError)
	return parts.hostname


def check_public(host: str) -> bool:
	"""True when every address the host resolves to is a public one."""
	try:
		addresses = _resolve(host)
	except OSError:
		return False
	return bool(addresses) and all(ipaddress.ip_address(a).is_global for a in addresses)


def sign(secret: str, timestamp: str, body: bytes) -> str:
	return "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


def settings() -> tuple[str, str]:
	"""The tenant's webhook address and secret ("" when not set)."""
	doc = frappe.get_doc(SETTINGS)
	return (doc.get(URL_FIELD) or "").strip(), doc.get_password(SECRET_FIELD, raise_exception=False) or ""


def _kind(before, doc) -> str | None:
	was, now = bool(before and before.published), bool(doc.published)
	if now and not was:
		return PUBLISHED
	if was and not now:
		return UNPUBLISHED
	if (
		now
		and before
		and (
			any(before.get(f) != doc.get(f) for f in WATCHED)
			or [m.media_asset for m in before.media] != [m.media_asset for m in doc.media]
		)
	):
		return UPDATED
	return None


def announce(doc, before):
	"""Called after a Listing is saved: queue a change call when the website is to be told."""
	kind = _kind(before, doc)
	if not kind:
		return
	url, secret = settings()
	if not url or not secret:
		return
	frappe.enqueue(
		"sellos.inventory.listing_webhook.deliver",
		queue="short",
		enqueue_after_commit=True,
		payload={"event": EVENT, "kind": kind, "listing": doc.name},
	)


def deliver(payload: dict) -> bool:
	"""Send one change call, trying up to MAX_ATTEMPTS times. True when the website answered 2xx."""
	url, secret = settings()
	if not url or not secret:
		return False
	try:
		host = check_url(url)
	except frappe.ValidationError:
		host = ""
	if not host or not check_public(host):
		frappe.log_error(
			title="Listings change webhook refused", message="The address is not a public https one."
		)
		return False
	body = json.dumps(
		{k: payload[k] for k in ("event", "kind", "listing")}, sort_keys=True, separators=(",", ":")
	).encode()
	status = 0
	for attempt in range(MAX_ATTEMPTS):
		timestamp = str(int(time.time()))
		headers = {
			"Content-Type": "application/json",
			"X-SellOS-Timestamp": timestamp,
			"X-SellOS-Signature": sign(secret, timestamp, body),
		}
		try:
			status = _post(url, body, headers)
		except requests.RequestException:
			status = 0
		if 200 <= status < 300:
			return True
		if attempt < MAX_ATTEMPTS - 1:
			_sleep(BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)])
	frappe.log_error(
		title="Listings change webhook failed",
		message=f"{payload.get('kind')} {payload.get('listing')}: last answer {status or 'none'}.",
	)
	return False
