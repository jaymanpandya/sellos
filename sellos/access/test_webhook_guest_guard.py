# SOS-LOOP (Jayman, 20 and 21 November 2026): two kinds of method may be called without a login. A
# provider webhook (registry `sellos.access.webhooks`, SOS-P2-06) and a public intake method (registry
# `sellos.access.public_intake`, built once by SOS-P2-08; it only creates or merges a lead through
# sellos.crm.intake). This test fails the build when a method in the sellos package allows guests and is
# in neither registry, or when a registered method does not declare every check.
# docs/permissions.md and CLAUDE.md ("Provider webhooks", "Public intake forms") hold the rules.
# Until SOS-P2-08 builds the intake registry, no public intake method exists.
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


def guest_methods_in_sellos():
	import_all_sellos_modules()
	return sorted(
		f"{fn.__module__}.{fn.__name__}"
		for fn in frappe.guest_methods
		if fn.__module__.startswith("sellos.") and ".test_" not in fn.__module__
	)


class TestGuestMethodsAreWebhooks(IntegrationTestCase):
	def test_every_guest_method_is_a_registered_webhook_or_public_intake(self):
		registered = {**registered_webhooks(), **registered_intakes()}
		unregistered = [path for path in guest_methods_in_sellos() if path not in registered]
		self.assertEqual(
			unregistered,
			[],
			"These methods allow guests but are neither registered provider webhooks nor registered public "
			"intake methods. A method without a login must be a webhook (signature check, replay "
			"protection, body cap, rate limit per tenant, per tenant secret) or a public intake method "
			"(write only, rate limits, honeypot, body cap, validation, form key, consent evidence). "
			"See docs/permissions.md, Provider webhooks and Public intake forms.",
		)

	def test_every_registered_webhook_declares_every_check(self):
		for path, checks in registered_webhooks().items():
			for name in REQUIRED_CHECKS:
				self.assertTrue(checks.get(name), f"{path} does not declare {name}")

	def test_every_registered_intake_declares_every_check(self):
		for path, checks in registered_intakes().items():
			for name in REQUIRED_INTAKE_CHECKS:
				self.assertTrue(checks.get(name), f"{path} does not declare {name}")

	def test_a_method_is_not_both_a_webhook_and_a_public_intake(self):
		both = set(registered_webhooks()) & set(registered_intakes())
		self.assertEqual(sorted(both), [], "a guest method is one kind, not both")

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
