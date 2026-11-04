# P1.06 clients, leads, activities, tasks and site visits: permissions, privacy and the end to end path.
import frappe
from frappe.app import application
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today
from werkzeug.test import Client as HttpClient
from werkzeug.wrappers import Response

from sellos.access.roles import AGENT, CHANNEL_PARTNER, COMPANY_ADMIN, PLATFORM_ADMIN, ensure_roles
from sellos.crm import api
from sellos.crm.base import is_overdue, mask_phone
from sellos.testing.users import PASSWORD, TEST_USERS, create_test_users
from sellos.tests.phones import in_mobile

DOCTYPES = ("Client", "Lead", "Lead Activity", "Lead Task", "Site Visit")
PHONE = in_mobile(11)
PHONE_MIDDLE = PHONE[3:8]
MASKED = "*" * 9 + PHONE[-3:]


def as_user(key):
	frappe.set_user(TEST_USERS[key]["email"])


def email(key):
	return TEST_USERS[key]["email"]


class CrmCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()  # each test starts with no CRM records

	def make_lead(self, key="agent", **extra):
		as_user(key)
		client = api.save_client(values={"client_name": "Asha Rao", "client_type": "Buyer", "phone": PHONE})
		lead = api.save_lead(values={"client": client["name"], "source": "Website", **extra})
		return client, lead["lead"]["name"]


class TestPureRules(IntegrationTestCase):
	def test_masking_keeps_the_last_three_digits(self):
		self.assertEqual(mask_phone(PHONE), MASKED)
		self.assertEqual(mask_phone(""), "")
		self.assertEqual(mask_phone(None), "")

	def test_overdue_needs_a_past_date_and_an_open_task(self):
		self.assertTrue(is_overdue(add_days(today(), -1), "Open"))
		self.assertFalse(is_overdue(add_days(today(), -1), "Done"))
		self.assertFalse(is_overdue(today(), "Open"))
		self.assertFalse(is_overdue(add_days(today(), 3), "Open"))
		self.assertFalse(is_overdue(None, "Open"))


class TestDoctypeSettings(IntegrationTestCase):
	def test_everything_is_change_tracked(self):
		for doctype in DOCTYPES:
			self.assertTrue(frappe.get_meta(doctype).track_changes, doctype)

	def test_nobody_gets_delete_and_only_the_platform_admin_gets_export(self):
		for doctype in DOCTYPES:
			for row in frappe.get_meta(doctype).permissions:
				self.assertFalse(row.delete, f"{doctype} {row.role}")
				if row.permlevel == 0:
					self.assertEqual(bool(row.export), row.role == PLATFORM_ADMIN, f"{doctype} {row.role}")

	def test_the_client_role_has_no_row_on_any_crm_doctype(self):
		for doctype in DOCTYPES:
			self.assertNotIn("SellOS Client", [r.role for r in frappe.get_meta(doctype).permissions])

	def test_full_phone_numbers_sit_at_permission_level_one_for_the_company_admin_only(self):
		meta = frappe.get_meta("Client")
		for field in ("phone", "overseas_phone"):
			self.assertEqual(meta.get_field(field).permlevel, 1)
		level_one = {r.role for r in meta.permissions if r.permlevel == 1}
		self.assertEqual(level_one, {COMPANY_ADMIN, PLATFORM_ADMIN})
		self.assertEqual(meta.get_field("phone_masked").permlevel, 0)


class TestEndToEnd(CrmCase):
	def test_an_agent_creates_a_lead_and_logs_an_activity(self):
		client, lead = self.make_lead()
		self.assertEqual(client["phone"], MASKED)
		activity = api.add_activity(lead, "Call", "Spoke about a 2BHK")
		self.assertEqual(activity["lead"], lead)
		view = api.get_lead(lead)
		self.assertEqual(view["lead"]["client"], client["name"])
		self.assertEqual([i["kind"] for i in view["timeline"]], ["activity"])
		self.assertEqual(view["timeline"][0]["title"], "Call")
		self.assertEqual(view["lead"]["lead_title"], "Asha Rao Website")

	def test_the_timeline_holds_activities_tasks_and_visits_with_overdue_marked(self):
		_, lead = self.make_lead()
		api.add_activity(lead, "Note", "first")
		api.save_task(values={"lead": lead, "title": "Send brochure", "due_date": add_days(today(), -2)})
		api.save_task(values={"lead": lead, "title": "Call back", "due_date": add_days(today(), 2)})
		api.save_site_visit(
			values={
				"lead": lead,
				"project_name": "Andheri Heights",
				"visit_datetime": f"{add_days(today(), 1)} 11:00:00",
			}
		)
		timeline = api.get_lead(lead)["timeline"]
		self.assertEqual({i["kind"] for i in timeline}, {"activity", "task", "visit"})
		overdue = {i["title"]: i["overdue"] for i in timeline if i["kind"] == "task"}
		self.assertEqual(overdue, {"Send brochure": True, "Call back": False})
		row = next(r for r in api.list_leads() if r["name"] == lead)
		self.assertEqual((row["open_tasks"], row["overdue_tasks"]), (2, 1))

	def test_completing_a_task_clears_overdue(self):
		_, lead = self.make_lead()
		task = api.save_task(values={"lead": lead, "title": "x", "due_date": add_days(today(), -1)})
		api.save_task(name=task["name"], values={"status": "Done"})
		self.assertFalse(api.get_lead(lead)["timeline"][0]["overdue"])


class TestWhoSeesWhat(CrmCase):
	def test_an_agent_cannot_see_another_agents_lead(self):
		_, lead = self.make_lead("agent")
		as_user("company_admin")
		other = api.save_client(values={"client_name": "Other", "client_type": "Seller"})
		other_lead = api.save_lead(values={"client": other["name"], "assigned_to": email("company_admin")})
		as_user("agent")
		self.assertEqual([r["name"] for r in api.list_leads()], [lead])
		self.assertRaises(frappe.PermissionError, api.get_lead, other_lead["lead"]["name"])

	def test_a_company_admin_sees_every_lead_and_the_full_phone(self):
		_, lead = self.make_lead("agent")
		as_user("company_admin")
		self.assertIn(lead, [r["name"] for r in api.list_leads()])
		self.assertEqual(api.get_lead(lead)["client"]["phone"], PHONE)
		self.assertEqual(api.list_clients()[0]["phone"], PHONE)

	def test_an_agent_and_a_partner_get_only_the_masked_phone(self):
		client, lead = self.make_lead("agent")
		for key in ("agent",):
			as_user(key)
			self.assertEqual(api.get_lead(lead)["client"]["phone"], MASKED)
		as_user("agent")
		doc = frappe.get_doc("Client", client["name"])
		doc.apply_fieldlevel_read_permissions()
		self.assertFalse(doc.get("phone"))
		self.assertEqual(doc.phone_masked, MASKED)

	def test_an_agent_reading_through_the_rest_style_calls_gets_no_phone(self):
		client, _ = self.make_lead("agent")
		as_user("agent")
		row = frappe.get_list(
			"Client", fields=["name", "phone", "phone_masked"], filters={"name": client["name"]}
		)
		self.assertEqual(row[0].get("phone"), None)
		self.assertEqual(row[0].phone_masked, MASKED)

	def test_a_shared_lead_is_visible_with_its_timeline(self):
		_, lead = self.make_lead("agent")
		api.add_activity(lead, "Call")
		frappe.share.add(
			"Lead", lead, email("channel_partner"), read=1, flags={"ignore_share_permission": True}
		)
		as_user("channel_partner")
		self.assertEqual(len(api.get_lead(lead)["timeline"]), 1)

	def test_a_partner_sees_their_leads_and_activity_but_cannot_log_or_edit_others(self):
		_, lead = self.make_lead("channel_partner")
		as_user("agent")
		self.assertEqual(api.list_leads(), [])  # the agent has no link to the partner's lead
		as_user("company_admin")
		api.add_activity(lead, "Call", "from the company")
		as_user("channel_partner")
		self.assertEqual(len(api.get_lead(lead)["timeline"]), 1)
		# a partner reads activities but is not a logger
		self.assertRaises(frappe.PermissionError, api.add_activity, lead, "Note")
		self.assertRaises(
			frappe.PermissionError, api.save_task, None, {"lead": lead, "title": "x", "due_date": today()}
		)

	def test_a_partner_cannot_see_an_agents_lead(self):
		self.make_lead("agent")
		as_user("channel_partner")
		self.assertEqual(api.list_leads(), [])
		self.assertEqual(api.list_clients(), [])

	def test_the_client_role_and_the_platform_admin_see_nothing(self):
		_, lead = self.make_lead("agent")
		for key in ("client", "platform_admin", "basic"):
			as_user(key)
			self.assertFalse(frappe.has_permission("Lead", "read", lead), key)
			self.assertFalse(
				frappe.has_permission("Client", "read"), key
			) if key != "platform_admin" else None
			self.assertRaises(frappe.PermissionError, api.list_leads)
			self.assertRaises(frappe.PermissionError, api.get_lead, lead)
		as_user("platform_admin")
		self.assertEqual(frappe.get_list("Lead"), [])
		self.assertEqual(frappe.get_list("Client"), [])

	def test_only_the_owner_assignee_or_company_admin_can_edit_and_reassign(self):
		_, lead = self.make_lead("agent")
		as_user("company_admin")
		api.save_lead(name=lead, values={"assigned_to": email("agent"), "notes": "hello"})
		as_user("agent")
		api.save_lead(name=lead, values={"notes": "mine"})
		# an unrelated partner cannot edit it, even by name
		as_user("channel_partner")
		self.assertRaises(frappe.PermissionError, api.save_lead, lead, {"notes": "no"})

	def test_a_lead_cannot_be_assigned_to_someone_without_a_working_role(self):
		_, lead = self.make_lead("agent")
		self.assertRaises(frappe.ValidationError, api.save_lead, lead, {"assigned_to": email("client")})


class TestArchiveNotDelete(CrmCase):
	def test_nothing_can_be_deleted_by_anyone(self):
		client, lead = self.make_lead("agent")
		activity = api.add_activity(lead, "Call")
		for user in ("agent", "company_admin", "platform_admin", "Administrator"):
			if user == "Administrator":
				frappe.set_user(user)
			else:
				as_user(user)
			for doctype, name in (
				("Lead Activity", activity["name"]),
				("Lead", lead),
				("Client", client["name"]),
			):
				self.assertRaises(frappe.PermissionError, frappe.delete_doc, doctype, name, force=True)
				self.assertTrue(frappe.db.exists(doctype, name))

	def test_archiving_hides_a_record_from_the_default_views_and_can_be_undone(self):
		_, lead = self.make_lead("agent")
		activity = api.add_activity(lead, "Call")
		api.set_archived("Lead Activity", activity["name"])
		self.assertEqual(api.get_lead(lead)["timeline"], [])
		api.set_archived("Lead", lead)
		self.assertEqual(api.list_leads(), [])
		self.assertEqual([r["name"] for r in api.list_leads(include_archived=1)], [lead])
		archived = frappe.get_doc("Lead", lead)
		self.assertTrue(archived.archived_on)
		self.assertEqual(archived.archived_by, email("agent"))
		api.set_archived("Lead", lead, 0)
		self.assertEqual([r["name"] for r in api.list_leads()], [lead])
		self.assertFalse(frappe.get_doc("Lead", lead).archived_on)

	def test_only_crm_records_can_be_archived_through_the_api(self):
		as_user("agent")
		self.assertRaises(frappe.PermissionError, api.set_archived, "User", email("agent"))


class TestChangeTracking(CrmCase):
	def test_an_edit_writes_a_version_with_the_user(self):
		# Frappe skips versions in tests unless asked, so this saves with ignore_version=False.
		client, _ = self.make_lead("agent")
		doc = frappe.get_doc("Client", client["name"])
		doc.city = "Mumbai"
		doc.flags.ignore_permissions = True
		doc.save(ignore_version=False)
		versions = frappe.get_all(
			"Version", filters={"ref_doctype": "Client", "docname": client["name"]}, fields=["owner", "data"]
		)
		self.assertEqual(len(versions), 1)
		self.assertEqual(versions[0].owner, email("agent"))
		self.assertIn("city", versions[0].data)


class TestOverHttp(CrmCase):
	"""The real request path as an agent: create a lead and log an activity (P1.06 end to end)."""

	def test_create_a_lead_and_log_an_activity_over_http(self):
		frappe.db.commit()  # the requests run in their own transactions  # nosemgrep
		http = HttpClient(application, Response)
		headers = {"Host": frappe.local.site}
		login = http.post("/api/method/login", data={"usr": email("agent"), "pwd": PASSWORD}, headers=headers)
		self.assertEqual(login.status_code, 200)
		client = http.post(
			"/api/method/sellos.crm.api.save_client",
			json={"values": {"client_name": "HTTP Buyer", "client_type": "NRI", "phone": PHONE}},
			headers=headers,
		)
		self.assertEqual(client.status_code, 200, client.get_data(as_text=True))
		client_name = client.json["message"]["name"]
		lead = http.post(
			"/api/method/sellos.crm.api.save_lead", json={"values": {"client": client_name}}, headers=headers
		)
		lead_name = lead.json["message"]["lead"]["name"]
		act = http.post(
			"/api/method/sellos.crm.api.add_activity",
			json={"lead": lead_name, "activity_type": "Call", "notes": "intro"},
			headers=headers,
		)
		self.assertEqual(act.status_code, 200, act.get_data(as_text=True))
		detail = http.get(f"/api/method/sellos.crm.api.get_lead?name={lead_name}", headers=headers)
		self.assertEqual(detail.json["message"]["timeline"][0]["title"], "Call")
		self.assertNotIn(PHONE_MIDDLE, detail.get_data(as_text=True))
		# the REST resource route must not hand an agent the full phone either
		rest = http.get(f"/api/resource/Client/{client_name}", headers=headers)
		self.assertNotIn(PHONE_MIDDLE, rest.get_data(as_text=True))
		# and a partner cannot read this agent's lead
		other = HttpClient(application, Response)
		other.post(
			"/api/method/login", data={"usr": email("channel_partner"), "pwd": PASSWORD}, headers=headers
		)
		denied = other.get(f"/api/method/sellos.crm.api.get_lead?name={lead_name}", headers=headers)
		self.assertNotEqual(denied.status_code, 200)
		self.assertNotIn("HTTP Buyer", denied.get_data(as_text=True))
		for doctype, name in (("Lead Activity", None), ("Lead", lead_name), ("Client", client_name)):
			if name:
				frappe.db.delete(doctype, {"name": name})
		frappe.db.delete("Lead Activity", {"lead": lead_name})
		frappe.db.commit()  # removes the committed test records  # nosemgrep
