"""SOS-P1-01: the control site. Tenant, Plan and Provisioning Job, their statuses, and who may open them."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from sellos.access.roles import ensure_roles
from sellos.provisioning import control, status
from sellos.testing.users import TEST_USERS, create_test_users

CUSTOMER_USERS = ("company_admin", "agent", "channel_partner", "client", "basic")
DOCTYPES = ("Tenant", "Plan", "Provisioning Job")


class TestStatusOrder(UnitTestCase):
	"""SOS-P1-01: the allowed order of statuses, without a database."""

	def test_the_four_statuses(self):
		self.assertEqual(status.STATUSES, ("Requested", "Provisioning", "Active", "Failed"))

	def test_every_allowed_change(self):
		allowed = {
			("Requested", "Provisioning"),
			("Provisioning", "Active"),
			("Provisioning", "Failed"),
			("Failed", "Provisioning"),
		}
		for old in status.STATUSES:
			for new in status.STATUSES:
				if old == new:
					continue
				with self.subTest(old=old, new=new):
					self.assertEqual(status.can_change(old, new), (old, new) in allowed)

	def test_an_active_record_never_moves(self):
		for new in status.STATUSES:
			if new != "Active":
				self.assertFalse(status.can_change("Active", new))

	def test_nothing_goes_back_to_requested(self):
		for old in ("Provisioning", "Active", "Failed"):
			self.assertFalse(status.can_change(old, "Requested"))


class TestControlSiteGuard(UnitTestCase):
	"""SOS-P1-01: company users cannot open the control site."""

	def test_only_a_platform_admin_or_the_bench_administrator_may_open_it(self):
		self.assertFalse(control.is_refused("a@example.com", ["SellOS Platform Admin"], "/sellos"))
		self.assertFalse(control.is_refused("Administrator", ["Administrator"], "/desk"))
		for role in ("SellOS Company Admin", "SellOS Agent", "SellOS Client", "SellOS Channel Partner"):
			with self.subTest(role=role):
				self.assertTrue(control.is_refused("a@example.com", [role], "/sellos"))
				self.assertTrue(control.is_refused("a@example.com", [role], "/api/resource/Tenant"))
		self.assertTrue(control.is_refused("a@example.com", [], "/sellos"))

	def test_a_signed_in_company_user_can_still_sign_out(self):
		self.assertFalse(control.is_refused("a@example.com", ["SellOS Agent"], "/api/method/logout"))

	def test_a_guest_is_left_to_the_login_page(self):
		self.assertFalse(control.is_refused("Guest", [], "/login"))

	def test_the_guard_runs_only_on_a_site_marked_as_the_control_site(self):
		with patch.object(frappe, "conf", frappe._dict()):
			self.assertFalse(control.is_control_site())
		with patch.object(frappe, "conf", frappe._dict(sellos_control_site=1)):
			self.assertTrue(control.is_control_site())

	def test_the_guard_is_a_before_request_hook(self):
		self.assertIn("sellos.provisioning.control.guard_control_site", frappe.get_hooks("before_request"))


class TestControlRecords(IntegrationTestCase):
	"""SOS-P1-01: a Platform Admin makes tenants, and the status follows the allowed order."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user(TEST_USERS["platform_admin"]["email"])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def tenant(self, tenant_id="p101acme", **values):
		return frappe.get_doc(
			{
				"doctype": "Tenant",
				"tenant_id": tenant_id,
				"company_name": "P101 Acme Realty",
				"admin_email": "owner@example.com",
				**values,
			}
		).insert()

	def test_a_platform_admin_creates_a_tenant_and_reads_it_back(self):
		self.tenant()
		saved = frappe.get_doc("Tenant", "p101acme")
		self.assertEqual(saved.status, "Requested")
		self.assertEqual(saved.site_name, "sellos_tenant_p101acme.localhost")
		self.assertEqual(saved.db_name, "sellos_tenant_p101acme")

	def test_creating_a_tenant_requests_a_provisioning_job(self):
		self.tenant()
		jobs = frappe.get_all(
			"Provisioning Job", filters={"tenant": "p101acme"}, fields=["status", "attempts"]
		)
		self.assertEqual([(j.status, j.attempts) for j in jobs], [("Requested", 0)])

	def test_a_tenant_id_that_is_not_safe_is_refused(self):
		for bad in ("Acme", "a b", "sellos_tenant_x", "../x", "", "a" * 60):
			with self.subTest(tenant_id=bad), self.assertRaises(frappe.ValidationError):
				self.tenant(bad)

	def test_a_tenant_id_is_unique(self):
		self.tenant()
		with self.assertRaises(frappe.DuplicateEntryError):
			self.tenant()

	def test_a_new_tenant_cannot_start_further_along(self):
		with self.assertRaises(frappe.ValidationError):
			self.tenant(status="Active")

	def test_a_tenant_follows_the_allowed_order(self):
		doc = self.tenant()
		for step in ("Provisioning", "Failed", "Provisioning", "Active"):
			doc.status = step
			doc.save()
			self.assertEqual(frappe.db.get_value("Tenant", "p101acme", "status"), step)

	def test_a_tenant_cannot_skip_a_step_or_leave_active(self):
		doc = self.tenant()
		doc.status = "Active"
		with self.assertRaises(frappe.ValidationError):
			doc.save()
		doc.reload()
		doc.status = "Provisioning"
		doc.save()
		doc.status = "Active"
		doc.save()
		for step in ("Requested", "Provisioning", "Failed"):
			doc.status = step
			with self.subTest(step=step), self.assertRaises(frappe.ValidationError):
				doc.save()
		self.assertEqual(frappe.db.get_value("Tenant", "p101acme", "status"), "Active")

	def test_a_tenant_id_cannot_change_after_it_is_made(self):
		doc = self.tenant()
		doc.tenant_id = "p101other"
		with self.assertRaises(frappe.ValidationError):
			doc.save()

	def test_a_job_follows_the_allowed_order_and_counts_attempts(self):
		self.tenant()
		job = frappe.get_doc("Provisioning Job", {"tenant": "p101acme"})
		with self.assertRaises(frappe.ValidationError):
			job.status = "Active"
			job.save()
		job.reload()
		job.status = "Provisioning"
		job.save()
		self.assertEqual(job.attempts, 1)
		self.assertTrue(job.started_at)
		job.status = "Failed"
		job.log = "step two failed"
		job.save()
		self.assertTrue(job.finished_at)
		job.status = "Provisioning"
		job.save()
		self.assertEqual(job.attempts, 2)
		self.assertFalse(job.finished_at)
		job.status = "Active"
		job.save()
		self.assertEqual(frappe.get_doc("Provisioning Job", job.name).status, "Active")

	def test_a_caller_cannot_set_the_attempt_count(self):
		self.tenant()
		job = frappe.get_doc("Provisioning Job", {"tenant": "p101acme"})
		job.attempts = 9
		job.save()
		self.assertEqual(frappe.get_doc("Provisioning Job", job.name).attempts, 0)

	def test_a_plan_is_made_and_a_tenant_may_not_use_a_switched_off_plan(self):
		frappe.get_doc({"doctype": "Plan", "plan_name": "P101 Trial", "max_users": 5}).insert()
		self.assertEqual(self.tenant(plan="P101 Trial").plan, "P101 Trial")
		frappe.get_doc({"doctype": "Plan", "plan_name": "P101 Old", "enabled": 0}).insert()
		with self.assertRaises(frappe.ValidationError):
			self.tenant("p101second", plan="P101 Old")

	def test_nothing_is_deleted_by_anyone(self):
		self.tenant()
		frappe.get_doc({"doctype": "Plan", "plan_name": "P101 Keep"}).insert()
		job = frappe.get_doc("Provisioning Job", {"tenant": "p101acme"})
		for doc in (frappe.get_doc("Tenant", "p101acme"), frappe.get_doc("Plan", "P101 Keep"), job):
			with self.subTest(doctype=doc.doctype), self.assertRaises(frappe.PermissionError):
				doc.delete()

	def test_the_statuses_are_the_four_agreed_ones(self):
		for doctype in ("Tenant", "Provisioning Job"):
			options = frappe.get_meta(doctype).get_field("status").options.split("\n")
			self.assertEqual(options, list(status.STATUSES))


class TestCompanyUsersAndTheControlSite(IntegrationTestCase):
	"""SOS-P1-01: a permission test. Company users get nothing from the control site records."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_a_company_user_cannot_read_create_or_write_any_control_record(self):
		for key in CUSTOMER_USERS:
			email = TEST_USERS[key]["email"]
			for doctype in DOCTYPES:
				for ptype in ("read", "write", "create", "delete", "export"):
					with self.subTest(user=key, doctype=doctype, ptype=ptype):
						self.assertFalse(frappe.has_permission(doctype, ptype, user=email))

	def test_a_company_user_cannot_create_a_tenant_through_the_resource_api(self):
		for key in CUSTOMER_USERS:
			frappe.set_user(TEST_USERS[key]["email"])
			with self.subTest(user=key), self.assertRaises(frappe.PermissionError):
				frappe.get_doc(
					{
						"doctype": "Tenant",
						"tenant_id": "p101evil",
						"company_name": "Evil",
						"admin_email": "x@example.com",
					}
				).insert()

	def test_a_company_user_sees_no_tenant_in_a_list(self):
		frappe.set_user("Administrator")
		frappe.get_doc(
			{
				"doctype": "Tenant",
				"tenant_id": "p101seen",
				"company_name": "Seen",
				"admin_email": "s@example.com",
			}
		).insert()
		for key in CUSTOMER_USERS:
			frappe.set_user(TEST_USERS[key]["email"])
			with self.subTest(user=key), self.assertRaises(frappe.PermissionError):
				frappe.get_list("Tenant")

	def test_the_platform_admin_has_the_permission(self):
		email = TEST_USERS["platform_admin"]["email"]
		for doctype in DOCTYPES:
			for ptype in ("read", "write", "create"):
				self.assertTrue(frappe.has_permission(doctype, ptype, user=email), f"{doctype} {ptype}")
			self.assertFalse(frappe.has_permission(doctype, "delete", user=email))
