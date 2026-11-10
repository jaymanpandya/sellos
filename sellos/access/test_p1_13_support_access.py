# SOS-P1-13 support access grants: a Company Admin gives a Platform Admin read access for up to 4
# hours, access ends at expiry, and every action is logged with the user and the time.
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, get_datetime, now_datetime

from sellos.access import support
from sellos.access.roles import ensure_roles
from sellos.testing.users import TEST_USERS, create_test_users
from sellos.tests import phones

ADMIN = TEST_USERS["company_admin"]["email"]
AGENT = TEST_USERS["agent"]["email"]
SUPPORT = TEST_USERS["platform_admin"]["email"]
CRM_DOCTYPES = ("Client", "Lead", "Lead Activity", "Lead Task", "Site Visit")


class SupportCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user(ADMIN)
		client = frappe.get_doc(
			{
				"doctype": "Client",
				"client_name": "P113 Buyer",
				"client_type": "Buyer",
				"phone": phones.in_mobile(113),
			}
		).insert()
		self.lead = frappe.get_doc({"doctype": "Lead", "client": client.name, "source": "Website"}).insert()
		self.client_name = client.name
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def grant(self, minutes=60):
		frappe.set_user(ADMIN)
		try:
			return support.grant_support_access(SUPPORT, minutes, "P1.13 test")
		finally:
			frappe.set_user("Administrator")

	def support_sees_leads(self):
		frappe.set_user(SUPPORT)
		try:
			return frappe.get_list("Lead", pluck="name")
		finally:
			frappe.set_user("Administrator")

	def log_actions(self, grant):
		return [
			r.action
			for r in frappe.get_all("Support Access Log", {"grant": grant}, ["action"], order_by="creation")
		]


class TestGrantAndExpiry(SupportCase):
	def test_sos_p1_13_a_one_hour_grant_works_and_then_ends(self):
		self.assertEqual(self.support_sees_leads(), [], "no grant, no data")
		grant = self.grant(60)
		self.assertEqual(grant["status"], "Active")
		self.assertEqual(grant["duration_minutes"], 60)
		self.assertIn(self.lead.name, self.support_sees_leads())

		with patch.object(support, "now_datetime", return_value=add_to_date(now_datetime(), minutes=59)):
			self.assertIn(self.lead.name, self.support_sees_leads(), "still active at 59 minutes")
		with patch.object(support, "now_datetime", return_value=add_to_date(now_datetime(), minutes=61)):
			self.assertEqual(self.support_sees_leads(), [], "ended at expiry, with no job run")
			self.assertIsNone(support.active_grant(SUPPORT))

	def test_the_grant_reads_every_crm_doctype_and_changes_nothing(self):
		self.grant(60)
		frappe.set_user(SUPPORT)
		for doctype in CRM_DOCTYPES:
			self.assertTrue(frappe.has_permission(doctype, "read"), doctype)
		doc = frappe.get_doc("Lead", self.lead.name)
		self.assertTrue(doc.has_permission("read"))
		for ptype in ("write", "create", "delete", "share", "export"):
			self.assertFalse(doc.has_permission(ptype), ptype)
		client = frappe.get_doc("Client", self.client_name)
		self.assertTrue(client.has_permission("read"))
		self.assertFalse(client.has_permission("write"))
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc({"doctype": "Lead", "client": self.client_name, "source": "Website"}).insert()
		doc.notes = "support edit"
		with self.assertRaises(frappe.PermissionError):
			doc.save()

	def test_a_support_user_without_a_grant_sees_nothing(self):
		frappe.set_user(SUPPORT)
		for doctype in CRM_DOCTYPES:
			self.assertEqual(frappe.get_list(doctype, pluck="name"), [], doctype)
		self.assertFalse(frappe.get_doc("Lead", self.lead.name).has_permission("read"))

	def test_a_grant_for_one_user_gives_nobody_else_access(self):
		self.grant(60)
		frappe.set_user(AGENT)
		self.assertNotIn(self.lead.name, frappe.get_list("Lead", pluck="name"))

	def test_a_grant_is_at_most_four_hours(self):
		frappe.set_user(ADMIN)
		for minutes in (0, -5, 241, 600):
			with self.assertRaises(frappe.ValidationError, msg=str(minutes)):
				support.grant_support_access(SUPPORT, minutes)
		view = support.grant_support_access(SUPPORT, 240)
		self.assertEqual(
			get_datetime(view["expires_at"]) - get_datetime(view["starts_at"]), timedelta(hours=4)
		)

	def test_a_stored_expiry_later_than_four_hours_is_still_cut_at_four_hours(self):
		grant = self.grant(60)
		starts = frappe.db.get_value("Support Grant", grant["name"], "starts_at")
		frappe.db.set_value("Support Grant", grant["name"], "expires_at", add_to_date(starts, hours=10))
		with patch.object(support, "now_datetime", return_value=add_to_date(starts, hours=4, minutes=1)):
			self.assertEqual(self.support_sees_leads(), [])
		with patch.object(support, "now_datetime", return_value=add_to_date(starts, hours=3, minutes=59)):
			self.assertIn(self.lead.name, self.support_sees_leads())

	def test_only_a_support_user_can_be_given_access(self):
		frappe.set_user(ADMIN)
		with self.assertRaises(frappe.ValidationError):
			support.grant_support_access(AGENT, 60)

	def test_the_start_and_author_are_set_by_the_server(self):
		doc = frappe.get_doc(
			{
				"doctype": "Support Grant",
				"support_user": SUPPORT,
				"duration_minutes": 30,
				"starts_at": add_to_date(now_datetime(), days=-5),
				"expires_at": add_to_date(now_datetime(), days=5),
				"granted_by": AGENT,
			}
		).insert(ignore_permissions=True)
		self.assertEqual(doc.granted_by, "Administrator")
		self.assertEqual(get_datetime(doc.expires_at) - get_datetime(doc.starts_at), timedelta(minutes=30))

	def test_revoking_ends_access_at_once(self):
		grant = self.grant(120)
		self.assertIn(self.lead.name, self.support_sees_leads())
		frappe.set_user(ADMIN)
		self.assertEqual(support.revoke_support_access(grant["name"])["status"], "Revoked")
		self.assertEqual(self.support_sees_leads(), [])
		frappe.set_user(ADMIN)
		self.assertEqual(support.revoke_support_access(grant["name"])["status"], "Revoked", "again is safe")
		self.assertEqual(self.log_actions(grant["name"]), ["Granted", "Revoked"])

	def test_the_scheduler_marks_an_ended_grant_expired_once(self):
		grant = self.grant(30)
		with patch.object(support, "now_datetime", return_value=add_to_date(now_datetime(), minutes=31)):
			support.expire_due_grants()
			support.expire_due_grants()
			status = [g["status"] for g in self.listed()]
		self.assertEqual(status, ["Expired"])
		self.assertEqual(frappe.db.get_value("Support Grant", grant["name"], "status"), "Expired")
		self.assertEqual(self.log_actions(grant["name"]), ["Granted", "Expired"])

	def listed(self):
		frappe.set_user(ADMIN)
		try:
			return support.list_support_grants()
		finally:
			frappe.set_user("Administrator")

	def test_the_list_shows_an_ended_grant_as_expired_before_the_scheduler_runs(self):
		self.grant(30)
		with patch.object(support, "now_datetime", return_value=add_to_date(now_datetime(), minutes=45)):
			frappe.set_user(ADMIN)
			rows = support.list_support_grants()
		self.assertEqual([r["status"] for r in rows], ["Expired"])


class TestEveryActionIsLogged(SupportCase):
	def request(self, path, method="GET", **form):
		frappe.set_user(SUPPORT)
		request = SimpleNamespace(path=path, method=method)
		with (
			patch.object(frappe.local, "request", request, create=True),
			patch.object(frappe.local, "form_dict", frappe._dict(form)),
			patch.object(frappe.db, "commit") as commit,
		):
			support.log_support_request()
		frappe.set_user("Administrator")
		return commit

	def lines(self, grant):
		return frappe.get_all(
			"Support Access Log",
			{"grant": grant},
			["user", "timestamp", "action", "http_method", "path", "reference_doctype", "reference_name"],
			order_by="creation",
		)

	def test_sos_p1_13_the_grant_and_every_request_are_logged_with_user_and_time(self):
		grant = self.grant(60)
		before = now_datetime()
		commit = self.request(f"/api/resource/Lead/{self.lead.name}")
		self.request("/api/method/frappe.client.get_list", "POST", doctype="Client")
		commit.assert_called()
		lines = self.lines(grant["name"])
		self.assertEqual([line.action for line in lines], ["Granted", "Request", "Request"])
		self.assertEqual(lines[0].user, ADMIN)
		for line in lines[1:]:
			self.assertEqual(line.user, SUPPORT)
			self.assertGreaterEqual(get_datetime(line.timestamp), get_datetime(before).replace(microsecond=0))
		self.assertEqual(
			(lines[1].http_method, lines[1].reference_doctype, lines[1].reference_name),
			("GET", "Lead", self.lead.name),
		)
		self.assertEqual((lines[2].http_method, lines[2].reference_doctype), ("POST", "Client"))

	def test_requests_are_not_logged_without_a_grant_or_by_other_users(self):
		self.request("/api/resource/Lead")
		self.assertEqual(frappe.db.count("Support Access Log"), 0)
		grant = self.grant(60)
		frappe.set_user(AGENT)
		with patch.object(frappe.local, "request", SimpleNamespace(path="/x", method="GET"), create=True):
			support.log_support_request()
		self.assertEqual(self.log_actions(grant["name"]), ["Granted"])

	def test_requests_after_expiry_are_not_logged_as_access(self):
		grant = self.grant(30)
		with patch.object(support, "now_datetime", return_value=add_to_date(now_datetime(), minutes=31)):
			self.request("/api/resource/Lead")
		self.assertEqual(self.log_actions(grant["name"]), ["Granted"])

	def test_the_company_admin_reads_the_log_of_a_grant(self):
		grant = self.grant(60)
		self.request(f"/api/resource/Lead/{self.lead.name}")
		frappe.set_user(ADMIN)
		rows = support.support_access_log(grant["name"])
		self.assertEqual([r["action"] for r in rows], ["Granted", "Request"])
		self.assertTrue(all(r["user"] and r["timestamp"] for r in rows))
		with self.assertRaises(frappe.DoesNotExistError):
			support.support_access_log("SUP-99999")

	def test_grants_and_log_lines_are_never_edited_or_deleted(self):
		grant = self.grant(60)
		doc = frappe.get_doc("Support Grant", grant["name"])
		with self.assertRaises(frappe.PermissionError):
			doc.delete()
		doc.expires_at = add_to_date(doc.expires_at, hours=3)
		with self.assertRaises(frappe.ValidationError):
			doc.save()
		line = frappe.get_doc("Support Access Log", frappe.get_all("Support Access Log", pluck="name")[0])
		line.action = "Revoked"
		with self.assertRaises(frappe.PermissionError):
			line.save()
		with self.assertRaises(frappe.PermissionError):
			line.delete()


class TestWhoMayManageGrants(SupportCase):
	def test_only_the_company_admin_grants_revokes_and_reads(self):
		grant = self.grant(60)
		for user in (AGENT, SUPPORT, TEST_USERS["client"]["email"], TEST_USERS["channel_partner"]["email"]):
			frappe.set_user(user)
			for call in (
				lambda: support.grant_support_access(SUPPORT, 60),
				lambda: support.revoke_support_access(grant["name"]),
				lambda: support.list_support_grants(),
				lambda: support.list_support_users(),
				lambda: support.support_access_log(grant["name"]),
			):
				with self.assertRaises(frappe.PermissionError, msg=user):
					call()

	def test_the_list_of_support_users_holds_the_platform_admin(self):
		frappe.set_user(ADMIN)
		self.assertIn(SUPPORT, [u["user"] for u in support.list_support_users()])
		self.assertNotIn(AGENT, [u["user"] for u in support.list_support_users()])
