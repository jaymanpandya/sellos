"""Public listings feed (SOS-P4-08): the third kind of method that may be called without a login.

The company's website reads its published listings here, with the "Listings read" key of the per company
key record (SOS-P1-09, `sellos.access.intake_keys`). The method is registered here with `public_listings`,
never with `@sellos_api`, and allows guests (`sellos/access/test_webhook_guest_guard.py` fails the build
otherwise). The rules are in CLAUDE.md ("Public listings feed") and docs/permissions.md. This module runs
every shared check once, in this order, so a feed supplies only its field allowlist and its reader:

1. Requests are limited per tenant, then per key (a minute window in the cache, before any database work).
2. The key is read from the `X-Listings-Key` header, never the URL, and must be the live key of the
   Listings read scope. A missing, wrong or other scope key (a Lead intake key) gets one short answer.
3. The page size is clamped to the cap.
4. The reader returns rows. Only the fields in the allowlist leave this module.
5. The answer carries an ETag. A request that sends the same tag in `If-None-Match` gets "not modified".

The tenant is the site the request arrives on, so no header, field or query can choose it. The method
only reads, sets no cookie and never returns a field outside its allowlist.
"""

import functools
import hashlib
import hmac
import json
import time

import frappe

from sellos.access import intake_keys
from sellos.access.webhooks import RATE_WINDOW_SECONDS

KEY_HEADER = "X-Listings-Key"
REFUSED_STATUS = 403
RATE_LIMITED_STATUS = 429
NOT_MODIFIED_STATUS = 304
# One short answer for every refusal of a key, so a caller learns nothing from it.
REFUSED_ANSWER = "refused"

_FEEDS: dict[str, dict] = {}

# Modules that register listings feeds (a fresh server process imports none of them when its first
# request arrives, so the request guard imports them to know the method is registered).
FEED_MODULES = ("sellos.inventory.listings_feed",)


def declared_listings_feeds() -> dict[str, dict]:
	"""Every registered public listings feed and the checks it declares."""
	return {path: dict(checks) for path, checks in _FEEDS.items()}


def load_feed_modules():
	import importlib

	for module in FEED_MODULES:
		importlib.import_module(module)


def is_public_listings(method_path: str | None) -> bool:
	if not method_path or not method_path.startswith("sellos."):
		return False
	load_feed_modules()
	return method_path in _FEEDS


def _count(kind: str, path: str, who: str, limit: int, now: float | None = None) -> bool:
	"""Count this request in the current minute. True when it is over the limit. The cache key carries
	the site, so every count is per tenant."""
	window = int((now if now is not None else time.time()) // RATE_WINDOW_SECONDS)
	key = frappe.cache.make_key(f"sellos_listings_rate:{kind}:{path}:{who}:{window}")
	count = frappe.cache.incrby(key, 1)
	if count == 1:
		frappe.cache.expire(key, RATE_WINDOW_SECONDS * 2)
	return count > limit


def etag_of(payload) -> str:
	body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
	return hashlib.sha256(body.encode()).hexdigest()[:32]


def _same_tag(sent: str | None, tag: str) -> bool:
	if not sent:
		return False
	for part in sent.split(","):
		part = part.strip()
		if part.startswith("W/"):
			part = part[2:]
		if part == "*" or hmac.compare_digest(part.strip('"').encode(), tag.encode()):
			return True
	return False


def _answer(status_code: int, answer=None):
	frappe.local.response["http_status_code"] = status_code
	return answer


def _page_number(value, default: int, low: int, high: int) -> int:
	try:
		number = int(value)
	except (TypeError, ValueError):
		return default
	return max(low, min(high, number))


def public_listings(*, field_allowlist, max_page_size, rate_limit_per_key, rate_limit_per_tenant):
	"""Register the decorated function as a public listings feed and whitelist it for guests.

	field_allowlist: the only fields a row may carry. A field is added here on purpose, never by default.
	max_page_size: the largest page; a larger request is clamped.
	rate_limit_per_key, rate_limit_per_tenant: requests a minute for one key and for the whole tenant.

	The decorated function takes (start, page_size) and returns the rows of that page of published
	listings, as dicts. It runs only for a request that passed every check, and it only reads."""
	if (
		not field_allowlist
		or min(max_page_size, rate_limit_per_key, rate_limit_per_tenant) < 1
		or not all(isinstance(name, str) and name for name in field_allowlist)
	):
		raise ValueError("a listings feed declares its field allowlist, page cap and rate limits")
	allowed = tuple(field_allowlist)

	def decorate(reader):
		path = f"{reader.__module__}.{reader.__name__}"
		_FEEDS[path] = {
			"read_only": "Never writes: it only reads published listings.",
			"published_only": "Only listings that are published and not archived.",
			"field_allowlist": list(allowed),
			"key_in_header": KEY_HEADER,
			"scope_listings_read": intake_keys.LISTINGS_READ,
			"uniform_refusal": REFUSED_ANSWER,
			"rate_limit_per_key": rate_limit_per_key,
			"rate_limit_per_tenant": rate_limit_per_tenant,
			"max_page_size": max_page_size,
			"etag": "SHA-256 of the answer; If-None-Match gets 304.",
		}

		@functools.wraps(reader)
		def endpoint():
			# Nothing here sets a cookie: drop the guest session cookie Frappe would add.
			manager = getattr(frappe.local, "cookie_manager", None)
			if manager is not None:
				manager.cookies.pop("sid", None)
			given = frappe.get_request_header(KEY_HEADER) or ""
			# 1. The limits, in the cache, before any database work. A key is counted by its hash.
			if _count("tenant", path, "all", rate_limit_per_tenant):
				return _answer(RATE_LIMITED_STATUS, "rate limited")
			digest = hashlib.sha256(given.encode()).hexdigest()[:24]
			if given and _count("key", path, digest, rate_limit_per_key):
				return _answer(RATE_LIMITED_STATUS, "rate limited")
			# 2. The key: the live Listings read key of this site, and nothing else.
			if not intake_keys.key_valid(given, intake_keys.LISTINGS_READ):
				return _answer(REFUSED_STATUS, REFUSED_ANSWER)
			# 3. The page, clamped. Only the allowlist leaves.
			form = frappe.local.form_dict
			size = _page_number(form.get("page_size"), max_page_size, 1, max_page_size)
			start = _page_number(form.get("start"), 0, 0, 10**9)
			rows = [{name: row[name] for name in allowed if name in row} for row in reader(start, size)]
			payload = {"listings": rows, "start": start, "page_size": size}
			# 4. The ETag.
			tag = etag_of(payload)
			frappe.local.flags.listings_etag = tag
			if _same_tag(frappe.get_request_header("If-None-Match"), tag):
				return _answer(NOT_MODIFIED_STATUS)
			return {**payload, "etag": tag}

		return frappe.whitelist(allow_guest=True, methods=["GET"])(endpoint)

	return decorate


def add_etag_header(response=None, request=None, **_ignored):
	"""after_request hook: carry the feed's ETag in the response header, and keep the answer private to
	the key's holder's cache rules (revalidate every time)."""
	tag = frappe.local.flags.get("listings_etag")
	if response is None or not tag:
		return
	response.headers["ETag"] = f'"{tag}"'
	response.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
