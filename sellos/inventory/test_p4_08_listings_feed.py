"""SOS-P4-08: the listings endpoint (contract tests) and the change webhook (change push tests)."""

import hashlib
import hmac
import json
import time
from unittest.mock import patch

import frappe
import requests
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from sellos.access import intake_keys, public_listings
from sellos.inventory import listing_webhook, listings, listings_feed
from sellos.inventory.test_p4_02_listing import FULL, ListingCase

METHOD = "sellos.inventory.listings_feed.published_listings"
PUBLIC_ADDRESS = "93.184.216.34"
SITE_URL = "https://site.example/hooks/listings"


def get_feed(key=None, query=None, headers=None):
	"""Call the feed as a guest, the way the website does. Returns (answer, status code)."""
	sent = dict(headers or {})
	if key is not None:
		sent[public_listings.KEY_HEADER] = key
	environ = EnvironBuilder(
		method="GET", path=f"/api/method/{METHOD}", base_url="https://tenant.example", headers=sent
	)
	frappe.local.request = Request(environ.get_environ())
	frappe.local.response = frappe._dict()
	frappe.local.flags.pop("listings_etag", None)
	frappe.set_user("Guest")
	frappe.local.form_dict = frappe._dict(query or {})
	try:
		answer = listings_feed.published_listings()
	finally:
		frappe.set_user("Administrator")
	return answer, frappe.local.response.get("http_status_code")


class FeedCase(ListingCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.key = intake_keys.make_key(intake_keys.LISTINGS_READ, "P408 test", replace=True)
		self.addCleanup(self.switch_off_keys)
		self.addCleanup(self.clear_counters)

	def switch_off_keys(self):
		for name in frappe.get_all(intake_keys.DOCTYPE, {"scope": intake_keys.LISTINGS_READ}, pluck="name"):
			frappe.db.set_value(intake_keys.DOCTYPE, name, "active", 0)

	def clear_counters(self):
		frappe.cache.delete_keys("sellos_listings_rate")

	def publish(self, **extra):
		name = self.make_listing(**extra)
		listings.publish_listing(name)
		return name


class TestOnlyPublishedListingsAreReturned(FeedCase):
	"""SOS-P4-08: only published listings are returned."""

	def test_a_published_listing_is_returned_and_a_draft_unpublished_or_archived_one_is_not(self):
		published = self.publish(title="P408 Published")
		draft = self.make_listing(title="P408 Draft")
		withdrawn = self.publish(title="P408 Withdrawn")
		listings.unpublish_listing(withdrawn)
		archived = self.publish(title="P408 Archived")
		listings.set_listing_archived(archived)
		frappe.set_user("Administrator")

		answer, status = get_feed(self.key)
		ids = [row["id"] for row in answer["listings"]]
		self.assertIsNone(status)
		self.assertIn(published, ids)
		for name in (draft, withdrawn, archived):
			self.assertNotIn(name, ids)

	def test_a_unit_listing_carries_its_project_and_a_property_listing_its_type(self):
		unit = self.make_unit()
		by_unit = self.publish(title="P408 Unit", listing_type="Primary", unit=unit, property=None)
		by_property = self.publish(title="P408 Property")
		frappe.set_user("Administrator")
		rows = {r["id"]: r for r in get_feed(self.key)[0]["listings"]}
		self.assertEqual(rows[by_unit]["project"], "P402 Tower")
		self.assertEqual(rows[by_property]["property_type"], "Apartment")
		self.assertEqual(rows[by_property]["asking_price"], FULL["asking_price"])


class TestFieldAllowlist(FeedCase):
	"""SOS-P4-08: only allowlisted fields leave. No owner, phone, mandate, notes or unpublished media."""

	def test_a_row_has_only_allowlisted_fields_and_no_internal_data(self):
		name = self.publish(title="P408 Fields")
		doc = frappe.get_doc("Listing", name)
		shown = frappe.get_doc(
			{
				"doctype": "Media Asset",
				"title": "P408 Shown",
				"media_type": "Photo",
				"file": "/files/p408-a.jpg",
			}
		).insert()
		hidden = frappe.get_doc(
			{
				"doctype": "Media Asset",
				"title": "P408 Archived photo",
				"media_type": "Photo",
				"file": "/files/p408-b.jpg",
				"archived": 1,
			}
		).insert()
		doc.append("media", {"media_asset": shown.name})
		doc.append("media", {"media_asset": hidden.name})
		doc.save()

		row = next(r for r in get_feed(self.key)[0]["listings"] if r["id"] == name)
		self.assertLessEqual(set(row), set(listings_feed.FIELD_ALLOWLIST))
		self.assertEqual(
			row["media"], [{"title": "P408 Shown", "media_type": "Photo", "url": "/files/p408-a.jpg"}]
		)
		text = json.dumps(row)
		for word in ("published_by", "changes", "owner", "seller", "phone", "mandate", "dossier", "notes"):
			self.assertNotIn(word, text.lower().replace("description", ""))
		self.assertNotIn(frappe.session.user, text)

	def test_the_allowlist_names_no_sensitive_field(self):
		for name in listings_feed.FIELD_ALLOWLIST:
			for word in ("owner", "seller", "phone", "mandate", "dossier", "note", "published_by", "changes"):
				self.assertNotIn(word, name)


class TestBadKeyIsRejected(FeedCase):
	"""SOS-P4-08: a bad key is rejected with one short answer."""

	def test_a_missing_wrong_other_scope_and_rotated_key_all_get_the_same_refusal(self):
		self.publish(title="P408 Secret title")
		lead_key = intake_keys.make_key(intake_keys.LEAD_INTAKE, "P408 lead key")
		old = self.key
		answers = []
		for given in (None, "", "wrong", lead_key, "x" * 500):
			answers.append(get_feed(given))
		for answer, status in answers:
			self.assertEqual((answer, status), ("refused", 403))
		# a key in the URL is never read
		self.assertEqual(get_feed(None, query={"key": old})[1], 403)
		self.assertEqual(get_feed(None, query={"key": old, "x-listings-key": old})[1], 403)
		# the right key works, and stops once rotated
		self.assertIsNone(get_feed(old)[1])
		intake_keys.make_key(intake_keys.LISTINGS_READ, "P408 new", replace=True)
		self.assertEqual(get_feed(old), ("refused", 403))

	def test_a_listings_key_never_creates_leads_and_a_lead_key_never_reads(self):
		self.assertFalse(intake_keys.key_valid(self.key, intake_keys.LEAD_INTAKE))
		lead_key = intake_keys.make_key(intake_keys.LEAD_INTAKE, "P408 lead key")
		self.assertFalse(intake_keys.key_valid(lead_key, intake_keys.LISTINGS_READ))
		self.addCleanup(
			lambda: [
				frappe.db.set_value(intake_keys.DOCTYPE, n, "active", 0)
				for n in frappe.get_all(intake_keys.DOCTYPE, {"scope": intake_keys.LEAD_INTAKE}, pluck="name")
			]
		)


class TestLimitsPagesCacheAndCookies(FeedCase):
	"""SOS-P4-08: rate limits per key and per tenant, a page cap, ETag caching, no cookie."""

	def test_the_page_size_is_clamped_and_a_page_starts_where_asked(self):
		for i in range(3):
			self.publish(title=f"P408 Page {i}")
		frappe.set_user("Administrator")
		answer, _status = get_feed(self.key, {"page_size": 1})
		self.assertEqual((len(answer["listings"]), answer["page_size"]), (1, 1))
		answer, _status = get_feed(self.key, {"page_size": 100000})
		self.assertEqual(answer["page_size"], listings_feed.MAX_PAGE_SIZE)
		answer, _status = get_feed(self.key, {"page_size": "abc", "start": "-4"})
		self.assertEqual((answer["page_size"], answer["start"]), (listings_feed.MAX_PAGE_SIZE, 0))

	def test_an_unchanged_request_gets_not_modified_and_a_change_gets_a_new_tag(self):
		name = self.publish(title="P408 Tagged")
		frappe.set_user("Administrator")
		first, status = get_feed(self.key)
		self.assertIsNone(status)
		self.assertEqual(
			first["etag"], public_listings.etag_of({k: first[k] for k in ("listings", "start", "page_size")})
		)
		again, status = get_feed(self.key, headers={"If-None-Match": f'"{first["etag"]}"'})
		self.assertEqual((again, status), (None, 304))
		response = Response()
		public_listings.add_etag_header(response=response)
		self.assertEqual(response.headers["ETag"], f'"{first["etag"]}"')
		listings.unpublish_listing(name)
		frappe.set_user("Administrator")
		changed, status = get_feed(self.key, headers={"If-None-Match": f'"{first["etag"]}"'})
		self.assertIsNone(status)
		self.assertNotEqual(changed["etag"], first["etag"])

	def test_the_tenant_and_the_key_are_each_rate_limited_before_the_key_is_checked(self):
		path = METHOD
		window = int(time.time() // 10**9)  # one window for the whole test, however long it takes
		with patch.object(public_listings, "RATE_WINDOW_SECONDS", 10**9):
			tenant_key = frappe.cache.make_key(f"sellos_listings_rate:tenant:{path}:all:{window}")
			frappe.cache.incrby(tenant_key, listings_feed.PER_TENANT_PER_MINUTE)
			self.assertEqual(get_feed("wrong"), ("rate limited", 429))
			self.assertEqual(get_feed(self.key), ("rate limited", 429))
			frappe.cache.delete(tenant_key)
			digest = hashlib.sha256(self.key.encode()).hexdigest()[:24]
			key_key = frappe.cache.make_key(f"sellos_listings_rate:key:{path}:{digest}:{window}")
			frappe.cache.incrby(key_key, listings_feed.PER_KEY_PER_MINUTE)
			self.assertEqual(get_feed(self.key), ("rate limited", 429))
			self.assertEqual(get_feed("wrong"), ("refused", 403))  # another key has its own count

	def test_it_sets_no_cookie_and_writes_nothing(self):
		self.publish(title="P408 Cookie")
		frappe.set_user("Administrator")
		frappe.local.cookie_manager = frappe.auth.CookieManager()
		frappe.local.cookie_manager.cookies["sid"] = {"value": "Guest"}
		before = {name: frappe.db.count(name) for name in ("Listing", "Lead", "Client", "Version")}
		get_feed(self.key)
		self.assertEqual(frappe.local.cookie_manager.cookies, {})
		self.assertEqual(before, {name: frappe.db.count(name) for name in before})

	def test_it_is_a_get_only_guest_method_with_every_check_declared(self):
		self.assertIn(listings_feed.published_listings, frappe.guest_methods)
		self.assertEqual(
			frappe.allowed_http_methods_for_whitelisted_func[listings_feed.published_listings], ["GET"]
		)
		self.assertTrue(public_listings.is_public_listings(METHOD))
		self.assertFalse(public_listings.is_public_listings("sellos.inventory.listings.save_listing"))


class WebhookCase(FeedCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(self.switch_off_webhook)
		with patch.object(listing_webhook, "_resolve", return_value=[PUBLIC_ADDRESS]):
			frappe.set_user("Administrator")
			self.secret = listings_feed.save_listings_webhook(SITE_URL)["webhook_secret"]

	def switch_off_webhook(self):
		frappe.set_user("Administrator")
		listings_feed.save_listings_webhook("")


class TestChangePush(WebhookCase):
	"""SOS-P4-08: changes trigger the webhook, which carries ids and the kind of change only."""

	def changes_of(self, action):
		with patch.object(frappe, "enqueue") as enqueue:
			action()
		return [call.kwargs["payload"] for call in enqueue.call_args_list]

	def test_publishing_changing_and_withdrawing_each_announce_a_change(self):
		name = self.make_listing(title="P408 Push")
		self.assertEqual(
			self.changes_of(lambda: listings.publish_listing(name)),
			[{"event": "listing.changed", "kind": "published", "listing": name}],
		)
		self.assertEqual(
			self.changes_of(lambda: listings.save_listing({"asking_price": 13000000}, name)),
			[{"event": "listing.changed", "kind": "updated", "listing": name}],
		)
		self.assertEqual(
			self.changes_of(lambda: listings.unpublish_listing(name)),
			[{"event": "listing.changed", "kind": "unpublished", "listing": name}],
		)

	def test_a_draft_edit_and_an_archive_of_a_draft_announce_nothing_and_archiving_a_published_one_withdraws_it(
		self,
	):
		draft = self.make_listing(title="P408 Draft push")
		self.assertEqual(
			self.changes_of(lambda: listings.save_listing({"title": "P408 Draft push 2"}, draft)), []
		)
		live = self.publish(title="P408 Live push")
		kinds = [p["kind"] for p in self.changes_of(lambda: listings.set_listing_archived(live))]
		self.assertEqual(kinds, ["unpublished"])

	def test_nothing_is_queued_when_no_webhook_is_set(self):
		listings_feed.save_listings_webhook("")
		name = self.make_listing(title="P408 No hook")
		self.assertEqual(self.changes_of(lambda: listings.publish_listing(name)), [])

	def test_the_call_is_signed_carries_ids_only_and_is_sent_once_when_it_works(self):
		sent = []

		def post(url, body, headers):
			sent.append((url, body, headers))
			return 200

		with (
			patch.object(listing_webhook, "_resolve", return_value=[PUBLIC_ADDRESS]),
			patch.object(listing_webhook, "_post", post),
		):
			self.assertTrue(
				listing_webhook.deliver(
					{"event": "listing.changed", "kind": "published", "listing": "LST-1", "title": "x"}
				)
			)
		((url, body, headers),) = sent
		self.assertEqual(url, SITE_URL)
		self.assertEqual(
			json.loads(body), {"event": "listing.changed", "kind": "published", "listing": "LST-1"}
		)
		expected = hmac.new(
			self.secret.encode(), headers["X-SellOS-Timestamp"].encode() + b"." + body, hashlib.sha256
		).hexdigest()
		self.assertEqual(headers["X-SellOS-Signature"], f"sha256={expected}")
		self.assertNotIn(self.secret, json.dumps(headers))

	def test_a_failed_call_is_retried_and_then_logged_without_the_secret(self):
		answers = iter([500, requests.ConnectionError("down"), 204])
		calls = []

		def post(url, body, headers):
			calls.append(1)
			answer = next(answers)
			if isinstance(answer, Exception):
				raise answer
			return answer

		payload = {"event": "listing.changed", "kind": "updated", "listing": "LST-2"}
		with (
			patch.object(listing_webhook, "_resolve", return_value=[PUBLIC_ADDRESS]),
			patch.object(listing_webhook, "_post", post),
			patch.object(listing_webhook, "_sleep") as sleep,
		):
			self.assertTrue(listing_webhook.deliver(payload))
		self.assertEqual((len(calls), sleep.call_count), (3, 2))

		with (
			patch.object(listing_webhook, "_resolve", return_value=[PUBLIC_ADDRESS]),
			patch.object(listing_webhook, "_post", return_value=503),
			patch.object(listing_webhook, "_sleep"),
			patch.object(frappe, "log_error") as log,
		):
			self.assertFalse(listing_webhook.deliver(payload))
		message = log.call_args.kwargs["message"]
		self.assertNotIn(self.secret, message)
		self.assertNotIn(SITE_URL, message)

	def test_a_private_address_is_never_called(self):
		for resolved in (
			["10.0.0.5"],
			["127.0.0.1"],
			["169.254.169.254"],
			[PUBLIC_ADDRESS, "192.168.1.9"],
			[],
		):
			with (
				self.subTest(resolved=resolved),
				patch.object(listing_webhook, "_resolve", return_value=resolved),
				patch.object(listing_webhook, "_post") as post,
				patch.object(frappe, "log_error"),
			):
				self.assertFalse(listing_webhook.deliver({"event": "e", "kind": "published", "listing": "L"}))
				post.assert_not_called()

	def test_a_redirect_is_never_followed(self):
		with patch.object(requests, "post") as post:
			post.return_value.status_code = 302
			self.assertEqual(listing_webhook._post(SITE_URL, b"{}", {}), 302)
		self.assertFalse(post.call_args.kwargs["allow_redirects"])


class TestAdminMethods(FeedCase):
	"""SOS-P4-08: a Company Admin makes the key and sets the webhook; each secret is shown once."""

	def test_the_key_is_returned_once_by_the_rotation_only(self):
		frappe.set_user("Administrator")
		out = listings_feed.rotate_listings_key()
		self.assertTrue(intake_keys.key_valid(out["key"], intake_keys.LISTINGS_READ))
		self.assertFalse(intake_keys.key_valid(self.key, intake_keys.LISTINGS_READ))
		again = listings_feed.get_listings_feed_settings()
		self.assertNotIn("key", again)
		self.assertNotIn(out["key"], json.dumps(again, default=str))
		self.assertNotIn(intake_keys.hash_key(out["key"]), json.dumps(again, default=str))
		self.assertEqual(again["key_header"], public_listings.KEY_HEADER)

	def test_the_webhook_address_must_be_a_public_https_one_and_the_secret_is_shown_once(self):
		frappe.set_user("Administrator")
		self.addCleanup(listings_feed.save_listings_webhook, "")
		for bad in (
			"http://site.example/x",
			"https://localhost/x",
			"https://10.0.0.1/x",
			"ftp://a.example",
			"https://u:p@a.example/",
		):
			with self.subTest(url=bad), self.assertRaises(frappe.ValidationError):
				listings_feed.save_listings_webhook(bad)
		first = listings_feed.save_listings_webhook(SITE_URL)
		self.assertTrue(first["webhook_secret"])
		self.assertEqual(first["webhook_url"], SITE_URL)
		kept = listings_feed.save_listings_webhook(SITE_URL)
		self.assertNotIn("webhook_secret", kept)
		self.assertTrue(kept["webhook_secret_set"])
		rotated = listings_feed.save_listings_webhook(SITE_URL, rotate_secret=1)
		self.assertNotEqual(rotated["webhook_secret"], first["webhook_secret"])
		self.assertNotIn("webhook_secret", listings_feed.get_listings_feed_settings())
