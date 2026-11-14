"""SOS-P1-16: find duplicates when a lead or client is entered, and merge two clients."""

import json

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access.matrix import MATRIX
from sellos.access.roles import AGENT, COMPANY_ADMIN
from sellos.crm import api, duplicates
from sellos.crm.base import mask_phone
from sellos.crm.test_crm import CrmCase, as_user, email
from sellos.patches import p1_16_client_phone_keys
from sellos.tests import phones

NUMBER = phones.in_mobile(61)
TEN = NUMBER[-10:]
OVERSEAS = phones.au_mobile(62)


def spaced(number):
	return f"{number[:3]} {number[3:8]} {number[8:]}"


def new_client(name="Dup Buyer", **values):
	return api.save_client(values={"client_name": name, "client_type": "Buyer", **values})


class TestNormalising(IntegrationTestCase):
	"""SOS-P1-16: one number, many spellings."""

	def test_every_spelling_of_an_indian_number_is_the_same_key(self):
		spellings = [
			NUMBER,
			spaced(NUMBER),
			NUMBER[1:],
			f"0{TEN}",
			TEN,
			f"{TEN[:5]} {TEN[5:]}",
			f"00{NUMBER[1:]}",
			f"+91-{TEN[:5]}-{TEN[5:]}",
			f"({NUMBER[:3]}) {TEN}",
		]
		for text in spellings:
			self.assertEqual(duplicates.normalise_phone(text), NUMBER, text)

	def test_an_overseas_number_keeps_its_own_country_code(self):
		for text in (OVERSEAS, spaced(OVERSEAS), OVERSEAS[1:], f"00{OVERSEAS[1:]}"):
			self.assertEqual(duplicates.normalise_phone(text), OVERSEAS, text)

	def test_another_number_and_unusable_text_are_different_or_empty(self):
		self.assertNotEqual(duplicates.normalise_phone(phones.near_in_mobile(61)), NUMBER)
		for text in (None, "", "abc", "12345"):
			self.assertEqual(duplicates.normalise_phone(text), "")

	def test_an_email_is_compared_without_case_or_spaces(self):
		self.assertEqual(duplicates.normalise_email("  Asha@Example.COM "), "asha@example.com")
		self.assertEqual(duplicates.normalise_email(None), "")


class TestMatching(CrmCase):
	"""SOS-P1-16: the one matching function."""

	def test_a_number_in_any_spelling_finds_the_client(self):
		client = new_client(phone=spaced(NUMBER))
		for text in (NUMBER, TEN, f"0{TEN}", NUMBER[1:], f"00{NUMBER[1:]}"):
			found = duplicates.find_matches(phone=text)
			self.assertEqual([m["name"] for m in found], [client["name"]], text)
			self.assertEqual(found[0]["matched_on"], ["phone"])

	def test_the_overseas_phone_and_the_email_match(self):
		client = new_client(overseas_phone=OVERSEAS, email="Dup.Person@example.com")
		by_overseas = duplicates.find_matches(overseas_phone=spaced(OVERSEAS))
		self.assertEqual(
			by_overseas, [{"name": client["name"], "matched_on": ["overseas_phone"], "archived": 0}]
		)
		by_email = duplicates.find_matches(email="dup.person@EXAMPLE.com")
		self.assertEqual(by_email[0]["matched_on"], ["email"])

	def test_a_number_typed_in_the_other_box_still_matches(self):
		client = new_client(phone=NUMBER, overseas_phone=OVERSEAS)
		self.assertEqual(duplicates.find_matches(phone=OVERSEAS)[0]["name"], client["name"])
		self.assertEqual(duplicates.find_matches(overseas_phone=NUMBER)[0]["matched_on"], ["phone"])

	def test_the_reasons_are_listed_and_the_best_match_comes_first(self):
		both = new_client("Both", phone=NUMBER, email="both@example.com")
		only_email = new_client("Only Email", email="both@example.com")
		found = duplicates.find_matches(phone=TEN, email="both@example.com")
		self.assertEqual([m["name"] for m in found], [both["name"], only_email["name"]])
		self.assertEqual(found[0]["matched_on"], ["phone", "email"])

	def test_a_different_number_and_an_empty_search_find_nothing(self):
		new_client(phone=NUMBER)
		self.assertEqual(duplicates.find_matches(phone=phones.near_in_mobile(61)), [])
		self.assertEqual(duplicates.find_matches(), [])
		self.assertEqual(duplicates.find_matches(phone="", email=" "), [])

	def test_the_client_being_edited_is_left_out(self):
		client = new_client(phone=NUMBER)
		self.assertEqual(duplicates.find_matches(phone=NUMBER, exclude=client["name"]), [])

	def test_an_archived_client_still_matches_and_says_so(self):
		client = new_client(phone=NUMBER)
		api.set_archived("Client", client["name"])
		self.assertEqual(duplicates.find_matches(phone=NUMBER)[0]["archived"], 1)

	def test_the_keys_follow_a_changed_number(self):
		client = new_client(phone=NUMBER)
		api.save_client(name=client["name"], values={"phone": phones.near_in_mobile(61)})
		self.assertEqual(duplicates.find_matches(phone=NUMBER), [])
		self.assertEqual(len(duplicates.find_matches(phone=phones.near_in_mobile(61))), 1)

	def test_the_patch_fills_the_keys_of_existing_clients_and_can_run_again(self):
		client = new_client(phone=spaced(NUMBER), overseas_phone=OVERSEAS)
		frappe.db.set_value("Client", client["name"], {"phone_key": "", "overseas_phone_key": ""})
		modified = frappe.db.get_value("Client", client["name"], "modified")
		for _ in range(2):
			p1_16_client_phone_keys.execute()
			keys = frappe.db.get_value("Client", client["name"], ["phone_key", "overseas_phone_key"])
			self.assertEqual(tuple(keys), (NUMBER, OVERSEAS))
		self.assertEqual(frappe.db.get_value("Client", client["name"], "modified"), modified)

	def test_the_keys_sit_at_permission_level_one(self):
		meta = frappe.get_meta("Client")
		for field in ("phone_key", "overseas_phone_key"):
			self.assertEqual(meta.get_field(field).permlevel, 1)
			self.assertTrue(meta.get_field(field).hidden)


class TestTheWarning(CrmCase):
	"""SOS-P1-16: what the viewer is shown, masked as the role requires."""

	def agents_lead(self, **values):
		as_user("agent")
		client = new_client("Asha Dup", phone=NUMBER)
		lead = api.save_lead(values={"client": client["name"], "source": "Website", **values})
		return client, lead["lead"]["name"]

	def other_agents_client(self, **values):
		as_user("company_admin")
		client = new_client("Someone Else", **values)
		api.save_lead(
			values={"client": client["name"], "source": "Bought list", "assigned_to": email("company_admin")}
		)
		as_user("agent")
		return client

	def test_an_agent_sees_their_client_and_its_leads_with_a_masked_phone(self):
		client, lead = self.agents_lead()
		found = api.find_duplicates(phone=spaced(NUMBER))
		self.assertEqual(len(found), 1)
		match = found[0]
		self.assertTrue(match["visible"])
		self.assertTrue(match["can_add"])
		self.assertEqual(match["name"], client["name"])
		self.assertEqual(match["phone"], mask_phone(NUMBER))
		self.assertEqual([lead_row["name"] for lead_row in match["leads"]], [lead])
		self.assertNotIn(NUMBER[-9:], json.dumps(found))

	def test_an_agent_is_told_about_a_client_they_cannot_see_and_never_gets_the_number(self):
		other = self.other_agents_client(phone=spaced(NUMBER), email="hidden@example.com")
		self.assertFalse(frappe.has_permission("Client", "read", doc=other["name"]))
		found = api.find_duplicates(phone=TEN, email="hidden@example.com")
		self.assertEqual(len(found), 1)
		match = found[0]
		self.assertFalse(match["visible"])
		self.assertFalse(match["can_add"])
		self.assertEqual(match["leads"], [])
		self.assertEqual(match["matched_on"], ["phone", "email"])
		self.assertEqual(match["phone"], mask_phone(NUMBER))
		text = json.dumps(found)
		for form in phones.forms(NUMBER):
			self.assertNotIn(form, text)
		self.assertNotIn("Someone Else", text)
		self.assertNotIn("hidden@example.com", text)
		self.assertNotIn("Bought list", text)

	def test_an_agent_sees_only_their_own_leads_of_a_shared_client(self):
		other = self.other_agents_client(phone=NUMBER)
		as_user("agent")
		mine = api.save_lead(values={"client": other["name"], "source": "Website"})["lead"]["name"]
		match = api.find_duplicates(phone=NUMBER)[0]
		self.assertTrue(match["visible"])
		self.assertEqual([lead["name"] for lead in match["leads"]], [mine])
		self.assertEqual(match["phone"], mask_phone(NUMBER))

	def test_a_company_admin_sees_every_match_with_the_full_number_and_it_is_logged(self):
		other = self.other_agents_client(phone=NUMBER)
		as_user("company_admin")
		frappe.db.delete("Access Log", {"method": "Full phone number shown"})
		match = api.find_duplicates(phone=TEN)[0]
		self.assertTrue(match["visible"])
		self.assertEqual(match["phone"], NUMBER)
		self.assertEqual(match["name"], other["name"])
		self.assertEqual(len(match["leads"]), 1)
		self.assertEqual(frappe.db.count("Access Log", {"method": "Full phone number shown"}), 1)

	def test_the_company_admin_and_the_agent_may_ask_and_the_others_may_not(self):
		self.assertEqual(MATRIX["sellos.crm.api.find_duplicates"], frozenset({AGENT, COMPANY_ADMIN}))
		self.assertEqual(MATRIX["sellos.crm.api.merge_clients"], frozenset({COMPANY_ADMIN}))
		as_user("channel_partner")
		with self.assertRaises(frappe.PermissionError):
			api.find_duplicates(phone=NUMBER)

	def test_adding_the_enquiry_to_the_existing_client_makes_a_second_lead_on_it(self):
		client, first = self.agents_lead()
		second = api.save_lead(values={"client": client["name"], "source": "Website"})["lead"]["name"]
		self.assertEqual(frappe.db.count("Client", {"phone_key": NUMBER}), 1)
		match = api.find_duplicates(phone=NUMBER)[0]
		self.assertEqual({lead["name"] for lead in match["leads"]}, {first, second})


class TestMerge(CrmCase):
	"""SOS-P1-16: a Company Admin merges two clients."""

	def two_clients(self):
		as_user("company_admin")
		keep = new_client("Keep Me", phone=NUMBER)
		merged = new_client("Merge Me", phone=phones.in_mobile(63), email="merge@example.com", city="Pune")
		lead = api.save_lead(values={"client": merged["name"], "source": "Website"})["lead"]["name"]
		activity = api.add_activity(lead, "Call", "first call")["name"]
		task = api.save_task(values={"lead": lead, "title": "Send brochure", "due_date": "2026-12-02"})[
			"name"
		]
		visit = api.save_site_visit(
			values={"lead": lead, "project_name": "Andheri Heights", "visit_datetime": "2026-12-01 11:00:00"}
		)["name"]
		kept_lead = api.save_lead(values={"client": keep["name"], "source": "Referral"})["lead"]["name"]
		return keep, merged, lead, kept_lead, (activity, task, visit)

	def test_leads_activities_tasks_and_visits_move_and_nothing_is_deleted(self):
		keep, merged, lead, kept_lead, (activity, task, visit) = self.two_clients()
		result = api.merge_clients(keep["name"], merged["name"])
		self.assertEqual(result, {"kept": keep["name"], "merged": merged["name"], "leads_moved": 1})
		self.assertEqual(frappe.db.get_value("Lead", lead, "client"), keep["name"])
		self.assertEqual(frappe.db.get_value("Lead", kept_lead, "client"), keep["name"])
		self.assertEqual(frappe.db.get_value("Lead Activity", activity, "lead"), lead)
		self.assertEqual(frappe.db.get_value("Lead Task", task, "lead"), lead)
		self.assertEqual(frappe.db.get_value("Site Visit", visit, "lead"), lead)
		self.assertFalse(frappe.get_all("Lead", filters={"client": merged["name"]}))
		view = api.get_lead(lead)
		self.assertEqual(view["client"]["name"], keep["name"])
		self.assertEqual({i["kind"] for i in view["timeline"]}, {"activity", "task", "visit"})
		for doctype, name in (("Client", merged["name"]), ("Lead", lead), ("Lead Activity", activity)):
			self.assertTrue(frappe.db.exists(doctype, name), doctype)

	def test_the_merged_client_is_archived_and_points_at_the_kept_one(self):
		keep, merged, *_ = self.two_clients()
		api.merge_clients(keep["name"], merged["name"])
		row = frappe.db.get_value("Client", merged["name"], ["archived", "merged_into"], as_dict=True)
		self.assertEqual((row.archived, row.merged_into), (1, keep["name"]))
		self.assertEqual(frappe.db.get_value("Client", keep["name"], "archived"), 0)

	def test_the_kept_client_gains_only_what_it_lacked(self):
		keep, merged, *_ = self.two_clients()
		api.merge_clients(keep["name"], merged["name"])
		doc = frappe.get_doc("Client", keep["name"])
		self.assertEqual(doc.phone, NUMBER)  # its own number stays
		self.assertEqual((doc.email, doc.city), ("merge@example.com", "Pune"))
		self.assertEqual(len(duplicates.find_matches(email="merge@example.com")), 2)

	def test_the_merge_is_logged_on_both_clients_and_in_the_lead_history(self):
		keep, merged, lead, *_ = self.two_clients()
		api.merge_clients(keep["name"], merged["name"])
		for name, other in ((keep["name"], merged["name"]), (merged["name"], keep["name"])):
			comments = frappe.get_all(
				"Comment",
				filters={"reference_doctype": "Client", "reference_name": name, "comment_type": "Info"},
				pluck="content",
			)
			self.assertTrue(any(other in text and "1 lead(s) moved" in text for text in comments), name)
		versions = frappe.get_all("Version", filters={"ref_doctype": "Lead", "docname": lead}, pluck="data")
		self.assertTrue(any(keep["name"] in data for data in versions))

	def test_no_number_appears_in_the_log(self):
		keep, merged, *_ = self.two_clients()
		api.merge_clients(keep["name"], merged["name"])
		texts = frappe.get_all("Comment", filters={"reference_doctype": "Client"}, pluck="content")
		for form in phones.forms(NUMBER) + phones.forms(phones.in_mobile(63)):
			self.assertFalse(any(form in text for text in texts), form)

	def test_only_a_company_admin_may_merge(self):
		keep, merged, *_ = self.two_clients()
		for role in ("agent", "channel_partner"):
			as_user(role)
			with self.assertRaises(frappe.PermissionError, msg=role):
				api.merge_clients(keep["name"], merged["name"])
		self.assertEqual(frappe.db.get_value("Client", merged["name"], "archived"), 0)

	def test_bad_merges_are_refused(self):
		keep, merged, *_ = self.two_clients()
		with self.assertRaises(frappe.ValidationError):
			api.merge_clients(keep["name"], keep["name"])
		api.merge_clients(keep["name"], merged["name"])
		with self.assertRaises(frappe.ValidationError):
			api.merge_clients(keep["name"], merged["name"])
		with self.assertRaises(frappe.ValidationError):
			api.merge_clients(merged["name"], keep["name"])

	def test_get_lead_tells_only_a_company_admin_it_can_merge(self):
		_, lead = self.make_lead("agent")
		self.assertFalse(api.get_lead(lead)["can_merge"])
		as_user("company_admin")
		self.assertTrue(api.get_lead(lead)["can_merge"])


class TestRegressionSeed(CrmCase):
	"""SOS-P1-16: the regression data holds one person entered twice, and seeding again adds no more."""

	def test_the_twin_clients_are_made_through_the_api_and_only_once(self):
		from sellos.tests import ui_fixtures

		admin, agent = email("company_admin"), email("agent")
		if frappe.db.exists("Client", {"client_name": f"{ui_fixtures.REGRESSION_PREFIX}Twin A"}):
			self.skipTest("the regression data is already on this site")
		for _ in range(2):
			ui_fixtures._seed_twin_clients(admin, agent)
		twins = frappe.get_all(
			"Client",
			filters={"client_name": ["like", f"{ui_fixtures.REGRESSION_PREFIX}Twin %"]},
			pluck="name",
		)
		self.assertEqual(len(twins), 2)
		found = duplicates.find_matches(email="regression_twin@example.com")
		self.assertEqual({m["name"] for m in found}, set(twins))
		for name in twins:
			leads = frappe.get_all("Lead", filters={"client": name}, pluck="name")
			self.assertEqual(len(leads), 1)
			self.assertEqual(frappe.db.count("Lead Activity", {"lead": leads[0]}), 1)
