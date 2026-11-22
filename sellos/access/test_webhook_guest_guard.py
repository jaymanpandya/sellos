# SOS-LOOP (Jayman, 20 and 21 November 2026): two kinds of method may be called without a login. A
# provider webhook (registry `sellos.access.webhooks`, SOS-P2-06) and a public intake method (registry
# `sellos.access.public_intake`, built once by SOS-P2-08; it only creates or merges a lead through
# sellos.crm.intake). This test fails the build when a method in the sellos package allows guests and is
# in neither registry, or when a registered method does not declare every check.
# A third kind (SOS-LOOP, 22 November 2026): a public listings feed (registry `sellos.access.public_listings`,
# built once by SOS-P4-08), the website reading published listings with the Listings read key.
# docs/permissions.md and CLAUDE.md ("Provider webhooks", "Public intake forms", "Public listings feed") hold the rules.
# SOS-P2-08 built the intake registry and the first public intake method, the enquiry page's submit.
import importlib

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access.test_permission_matrix import import_all_sellos_modules

# What every registered webhook declares (the rules in docs/permissions.md). A value of None or False,
# or a missing key, fails.
REQUIRED_CHECKS = (
	"signature",  # the name of the signature check, run before any database work
	"replay",  # how a replayed or out of order event is ignored
	"max_body_bytes",  # the body size cap
	"rate_limit_per_tenant",  # requests per minute, per tenant
	"secret_setting",  # the company settings field that holds the tenant's signing secret
)


def registered_webhooks():
	try:
		module = importlib.import_module("sellos.access.webhooks")
	except ModuleNotFoundError:
		return {}
	return module.declared_webhooks()


# What every registered public intake method declares (docs/permissions.md, "Public intake forms").
# A value of None or False, or a missing key, fails.
REQUIRED_INTAKE_CHECKS = (
	"write_only",  # answers a thank you and a reference code only
	"rate_limit_per_address",  # requests per minute per address
	"rate_limit_per_tenant",  # requests per minute per tenant
	"honeypot_field",  # the name of the honeypot field
	"max_body_bytes",  # the body size cap
	"field_validation",  # the strict validation of the fields
	"form_key_setting",  # the per tenant form key a Company Admin can rotate
	"consent_evidence",  # wording, version, time and address saved as a private file
	"calls_intake",  # it only creates or merges a lead through sellos.crm.intake
)


def registered_intakes():
	try:
		module = importlib.import_module("sellos.access.public_intake")
	except ModuleNotFoundError:
		return {}
	return module.declared_intakes()


# What every registered public listings feed declares (docs/permissions.md, "Public listings feed").
# A value of None or False, or a missing key, fails.
REQUIRED_LISTINGS_CHECKS = (
	"read_only",  # never writes
	"published_only",  # only published listings
	"field_allowlist",  # the explicit list of returned fields (no owner, phone, mandate, notes, unpublished media)
	"key_in_header",  # the Listings read key is read from a header, never the URL
	"scope_listings_read",  # only a Listings read key; a Lead intake key is refused
	"uniform_refusal",  # a bad key gets one short answer that reveals nothing
	"rate_limit_per_key",  # requests per minute per key
	"rate_limit_per_tenant",  # requests per minute per tenant
	"max_page_size",  # the page size cap
	"etag",  # caching with ETag
)


def registered_listings_feeds():
	try:
		module = importlib.import_module("sellos.access.public_listings")
	except ModuleNotFoundError:
		return {}
	return module.declared_listings_feeds()


def guest_methods_in_sellos():
	import_all_sellos_modules()
	return sorted(
		f"{fn.__module__}.{fn.__name__}"
		for fn in frappe.guest_methods
		if fn.__module__.startswith("sellos.") and ".test_" not in fn.__module__
	)


class TestGuestMethodsAreWebhooks(IntegrationTestCase):
	def test_every_guest_method_is_a_registered_webhook_intake_or_listings_feed(self):
		registered = {**registered_webhooks(), **registered_intakes(), **registered_listings_feeds()}
		unregistered = [path for path in guest_methods_in_sellos() if path not in registered]
		self.assertEqual(
			unregistered,
			[],
			"These methods allow guests but are not registered provider webhooks, registered public "
			"intake methods or registered public listings feeds. A method without a login must be a "
			"webhook (signature check, replay protection, body cap, rate limit per tenant, per tenant "
			"secret), a public intake method (write only, rate limits, honeypot, body cap, validation, "
			"form key, consent evidence) or a public listings feed (read only, published only, field "
			"allowlist, key in a header, uniform refusal, rate limits, page cap, ETag). See "
			"docs/permissions.md, Provider webhooks, Public intake forms and Public listings feed.",
		)

	def test_every_registered_webhook_declares_every_check(self):
		for path, checks in registered_webhooks().items():
			for name in REQUIRED_CHECKS:
				self.assertTrue(checks.get(name), f"{path} does not declare {name}")

	def test_every_registered_intake_declares_every_check(self):
		for path, checks in registered_intakes().items():
			for name in REQUIRED_INTAKE_CHECKS:
				self.assertTrue(checks.get(name), f"{path} does not declare {name}")

	def test_every_registered_listings_feed_declares_every_check(self):
		for path, checks in registered_listings_feeds().items():
			for name in REQUIRED_LISTINGS_CHECKS:
				self.assertTrue(checks.get(name), f"{path} does not declare {name}")

	def test_a_method_is_only_one_kind(self):
		kinds = (set(registered_webhooks()), set(registered_intakes()), set(registered_listings_feeds()))
		for i, a in enumerate(kinds):
			for b in kinds[i + 1 :]:
				self.assertEqual(sorted(a & b), [], "a guest method is one kind, not two")

	def test_a_registered_listings_feed_is_also_a_guest_method(self):
		import_all_sellos_modules()
		guests = set(guest_methods_in_sellos())
		for path in registered_listings_feeds():
			self.assertIn(path, guests, f"{path} is registered as a listings feed but does not allow guests")

	def test_a_registered_intake_is_also_a_guest_method(self):
		import_all_sellos_modules()
		guests = set(guest_methods_in_sellos())
		for path in registered_intakes():
			self.assertIn(path, guests, f"{path} is registered as public intake but does not allow guests")

	def test_a_registered_webhook_is_also_a_guest_method(self):
		"""A registration with no guest access is a mistake: it hides the method from the other checks."""
		import_all_sellos_modules()
		guests = set(guest_methods_in_sellos())
		for path in registered_webhooks():
			self.assertIn(path, guests, f"{path} is registered as a webhook but does not allow guests")


class TestRealIntakeMethodIsRegistered(IntegrationTestCase):
	"""SOS-P2-08: the enquiry page's submit is a real registered public intake method with every check."""

	METHOD = "sellos.crm.enquiry.submit_enquiry"

	def test_the_enquiry_submit_is_registered_and_declares_every_check(self):
		intakes = registered_intakes()
		self.assertIn(self.METHOD, intakes)
		for name in REQUIRED_INTAKE_CHECKS:
			self.assertTrue(intakes[self.METHOD].get(name), f"{self.METHOD} does not declare {name}")

	def test_it_is_the_only_guest_method_besides_webhooks(self):
		extra = set(guest_methods_in_sellos()) - set(registered_webhooks())
		# SOS-P1-09 added the website form's submit as the second one. SOS-P4-08 added the listings feed.
		self.assertEqual(
			sorted(extra),
			[
				self.METHOD,
				"sellos.crm.website_form.submit_website_lead",
				"sellos.inventory.listings_feed.published_listings",
			],
		)


class TestRealListingsFeedIsRegistered(IntegrationTestCase):
	"""SOS-P4-08: the website's listings read is a real registered public listings feed with every check."""

	METHOD = "sellos.inventory.listings_feed.published_listings"

	def test_the_feed_is_registered_declares_every_check_and_is_a_guest_method(self):
		feeds = registered_listings_feeds()
		self.assertIn(self.METHOD, feeds)
		for name in REQUIRED_LISTINGS_CHECKS:
			self.assertTrue(feeds[self.METHOD].get(name), f"{self.METHOD} does not declare {name}")
		self.assertIn(self.METHOD, guest_methods_in_sellos())

	def test_a_guest_method_that_is_not_registered_would_be_found(self):
		"""The check names a stray guest method: a feed registered nowhere is reported."""
		registered = {**registered_webhooks(), **registered_intakes(), **registered_listings_feeds()}
		self.assertNotIn("sellos.inventory.listings_feed.stray", registered)
		self.assertIn(self.METHOD, registered)
