# SOS-LOOP (Jayman, 20 November 2026): a provider webhook is the one kind of method that may be called
# without a login, and only when it is registered as a webhook with its checks. This test fails the build
# when a method in the sellos package allows guests and is not in the webhook registry, or when a
# registered webhook does not declare every check. docs/permissions.md ("Provider webhooks") and
# CLAUDE.md ("Provider webhooks") hold the rules. The registry is `sellos.access.webhooks` (built by
# SOS-P2-06); until it exists no sellos method may allow guests.
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


def guest_methods_in_sellos():
	import_all_sellos_modules()
	return sorted(
		f"{fn.__module__}.{fn.__name__}"
		for fn in frappe.guest_methods
		if fn.__module__.startswith("sellos.") and ".test_" not in fn.__module__
	)


class TestGuestMethodsAreWebhooks(IntegrationTestCase):
	def test_every_guest_method_is_a_registered_webhook(self):
		registered = registered_webhooks()
		unregistered = [path for path in guest_methods_in_sellos() if path not in registered]
		self.assertEqual(
			unregistered,
			[],
			"These methods allow guests but are not registered provider webhooks. A method without a "
			"login must be a webhook with a signature check, replay protection, a body cap, a rate limit "
			"per tenant and a per tenant secret (docs/permissions.md, Provider webhooks).",
		)

	def test_every_registered_webhook_declares_every_check(self):
		for path, checks in registered_webhooks().items():
			for name in REQUIRED_CHECKS:
				self.assertTrue(checks.get(name), f"{path} does not declare {name}")

	def test_a_registered_webhook_is_also_a_guest_method(self):
		"""A registration with no guest access is a mistake: it hides the method from the other checks."""
		import_all_sellos_modules()
		guests = set(guest_methods_in_sellos())
		for path in registered_webhooks():
			self.assertIn(path, guests, f"{path} is registered as a webhook but does not allow guests")
