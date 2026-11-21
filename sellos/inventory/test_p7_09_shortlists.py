"""SOS-P7-09: shortlists and sharing with buyers. Building and ordering a shortlist, the note on each home, sharing
as a link or a PDF (with no other client's data and no phone number but the agent's), the opened marks, what is
marked as no longer available, and who may see which shortlist."""

from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access.roles import ensure_roles
from sellos.crm import api as crm
from sellos.inventory import api, listings, media, pricing, shortlists, structure
from sellos.inventory.cost_sheet import inr
from sellos.inventory.plain_pdf import build_shortlist_pdf
from sellos.inventory.test_p4_01_inventory import InventoryCase, _as
from sellos.inventory.test_p4_03_media import JPEG, b64
from sellos.testing.users import TEST_USERS, create_test_users
from sellos.tests import phones

AGENT_PHONE = phones.in_mobile(7091)
OTHER_PHONE = phones.in_mobile(7092)


class ShortlistCase(InventoryCase):
	def setUp(self):
		super().setUp()
		before = set(Path(frappe.get_site_path("public", "files")).glob("media-*"))
		self.addCleanup(self.remove_files, before)
		self.agent = TEST_USERS["agent"]["email"]
		self.manager = TEST_USERS["sales_manager"]["email"]
		self.client_user = TEST_USERS["client"]["email"]
		frappe.db.set_value("User", self.agent, "mobile_no", AGENT_PHONE)
		self.project = self.make_project("P709 Project", rera="P51800070901", developer="P709 Developer")
		frappe.db.set_value("Project", self.project, "locality", "Powai")
		tower = structure.add_tower(self.project, "Tower S", "1 to 1")["name"]
		structure.generate_floor_units(tower, 1, "101 to 103", 640, "2 BHK", "S")
		self.units = {u["unit_number"]: u["name"] for u in api.get_project(self.project)["units"]}
		pricing.save_price_list(
			self.project, {"title": "P709 prices", "effective_from": "2020-01-01", "base_rate": 12500}
		)
		self.listing = self.publish_listing()
		self.buyer = self.make_client("P709 Buyer", self.client_user, 7093)
		self.other = self.make_client("P709 Other Buyer", "p709-other@example.com", 7094)
		self.lead = self.make_lead(self.buyer, self.agent)
		self.other_lead = self.make_lead(self.other, self.agent)

	@staticmethod
	def remove_files(before):
		for path in set(Path(frappe.get_site_path("public", "files")).glob("media-*")) - before:
			path.unlink()

	def make_client(self, name, email, seed):
		return crm.save_client(
			values={
				"client_name": name,
				"client_type": "Buyer",
				"email": email,
				"phone": phones.in_mobile(seed) if name != "P709 Other Buyer" else OTHER_PHONE,
			}
		)["name"]

	def make_lead(self, client, owner):
		return crm.save_lead(
			values={
				"client": client,
				"source": "Website",
				"assigned_to": owner,
				"configuration": ["2 BHK"],
				"property_type": "Apartment",
				"preferred_localities": ["Powai"],
			}
		)["lead"]["name"]

	def publish_listing(self):
		prop = api.save_property(
			{
				"title": "P709 Powai Flat",
				"property_type": "Apartment",
				"city": "Mumbai",
				"locality": "Powai",
				"configuration": "2 BHK",
				"carpet_area": 700,
			}
		)["name"]
		name = listings.save_listing(
			{
				"title": "P709 Listing",
				"listing_type": "Direct",
				"property": prop,
				"asking_price": 7_500_000,
				"description": "A bright flat",
			}
		)["name"]
		media.upload_listing_media(name, "Front view", "front.jpg", b64(JPEG))
		listings.publish_listing(name)
		return name

	def build(self, *homes, owner="agent"):
		"""A shortlist of the buyer's lead made by the agent with the given (kind, target) homes."""
		_as(owner)
		name = shortlists.create_shortlist(lead=self.lead)["name"]
		for kind, target in homes:
			shortlists.add_to_shortlist(kind, target, shortlist=name)
		return shortlists.get_shortlist(name)

	def items(self, view):
		return {i["title"]: i for i in view["items"]}


class TestBuildingAShortlist(ShortlistCase):
	"""SOS-P7-09: an agent makes a shortlist for one client from listings and units, orders it and adds a note."""

	def test_a_shortlist_is_made_for_the_leads_client_with_the_agent_as_its_maker(self):
		_as("agent")
		view = shortlists.create_shortlist(lead=self.lead)
		self.assertEqual((view["client"], view["agent"], view["lead"]), (self.buyer, self.agent, self.lead))
		self.assertEqual((view["title"], view["items"], view["shared"]), ("Homes for P709 Buyer", [], False))

	def test_units_and_listings_are_added_in_order_with_their_prices_and_photos(self):
		view = self.build(
			("Unit", self.units["S102"]), ("Listing", self.listing), ("Unit", self.units["S101"])
		)
		self.assertEqual(
			[(i["position"], i["kind"], i["title"]) for i in view["items"]],
			[
				(1, "Unit", "P709 Project, unit S102"),
				(2, "Listing", "P709 Listing"),
				(3, "Unit", "P709 Project, unit S101"),
			],
		)
		self.assertEqual([i["price"] for i in view["items"]], [8_000_000, 7_500_000, 8_000_000])
		self.assertEqual(len(view["items"][1]["photos"]), 1)
		self.assertTrue(view["items"][1]["photos"][0].startswith("/files/media-"))

	def test_a_home_is_added_once(self):
		view = self.build(("Unit", self.units["S101"]))
		again = shortlists.add_to_shortlist("Unit", self.units["S101"], shortlist=view["name"])
		self.assertEqual((again["added"], again["item_count"]), (False, 1))

	def test_adding_from_a_lead_uses_the_open_shortlist_and_makes_one_when_there_is_none(self):
		_as("agent")
		first = shortlists.add_to_shortlist("Unit", self.units["S101"], lead=self.lead)
		second = shortlists.add_to_shortlist("Listing", self.listing, lead=self.lead)
		self.assertEqual((first["name"], first["added"]), (second["name"], True))
		self.assertEqual(second["item_count"], 2)
		self.assertEqual(len(shortlists.list_shortlists(lead=self.lead)["shortlists"]), 1)

	def test_the_order_is_changed_and_must_list_every_home_once(self):
		view = self.build(
			("Unit", self.units["S101"]), ("Unit", self.units["S102"]), ("Unit", self.units["S103"])
		)
		a, b, c = (i["name"] for i in view["items"])
		moved = shortlists.reorder_shortlist(view["name"], [c, a, b])
		self.assertEqual([i["name"] for i in moved["items"]], [c, a, b])
		self.assertEqual([i["position"] for i in moved["items"]], [1, 2, 3])
		for bad in ([a, b], [a, b, b], [a, b, c, c]):
			with self.subTest(order=bad), self.assertRaises(frappe.ValidationError):
				shortlists.reorder_shortlist(view["name"], bad)

	def test_each_home_takes_a_note_and_a_home_is_taken_off(self):
		view = self.build(("Unit", self.units["S101"]), ("Unit", self.units["S102"]))
		first, second = (i["name"] for i in view["items"])
		noted = shortlists.save_item_note(view["name"], first, "  Corner flat,   park facing ")
		self.assertEqual(noted["items"][0]["note"], "Corner flat, park facing")
		removed = shortlists.remove_shortlist_item(view["name"], first)
		self.assertEqual([i["name"] for i in removed["items"]], [second])
		self.assertEqual(shortlists.remove_shortlist_item(view["name"], first)["item_count"], 1)

	def test_only_an_available_unit_or_a_published_listing_goes_on(self):
		api.set_inventory_status("Unit", self.units["S103"], "Held")
		draft = listings.save_listing(
			{"title": "P709 Draft", "listing_type": "Primary", "unit": self.units["S102"], "asking_price": 1}
		)["name"]
		view = self.build()
		for kind, target in (("Unit", self.units["S103"]), ("Listing", draft), ("House", self.listing)):
			with self.subTest(kind=kind), self.assertRaises(frappe.ValidationError):
				shortlists.add_to_shortlist(kind, target, shortlist=view["name"])
		with self.assertRaises(frappe.DoesNotExistError):
			shortlists.add_to_shortlist("Unit", "no-such-unit", shortlist=view["name"])

	def test_a_shortlist_is_for_a_lead_of_the_same_client_and_is_never_deleted(self):
		_as("agent")
		with self.assertRaises(frappe.ValidationError):
			shortlists.create_shortlist(client=self.other, lead=self.lead)
		name = shortlists.create_shortlist(lead=self.lead)["name"]
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Shortlist", name)
		archived = shortlists.archive_shortlist(name)
		self.assertTrue(archived["archived"])
		with self.assertRaises(frappe.ValidationError):
			shortlists.update_shortlist(name, title="Changed")
		self.assertFalse(shortlists.archive_shortlist(name, 0)["archived"])


class TestSharing(ShortlistCase):
	"""SOS-P7-09: sharing sends the client a link to their own view, or a PDF with the branding, photos and prices."""

	def share(self, view, via="Link", mail=False):
		_as("agent")
		sent = []
		with (
			patch("sellos.access.users.mail_ready", return_value=mail),
			patch("frappe.sendmail", side_effect=lambda **kw: sent.append(kw)),
		):
			return shortlists.share_shortlist(view["name"], via), sent

	def test_a_draft_is_not_seen_by_the_client_and_a_shared_one_is(self):
		view = self.build(("Unit", self.units["S101"]), ("Listing", self.listing))
		_as("client")
		self.assertEqual(shortlists.my_shortlists(), {"shortlists": []})
		with self.assertRaises(frappe.PermissionError):
			shortlists.my_shortlist(view["name"])
		result, _sent = self.share(view)
		_as("client")
		mine = shortlists.my_shortlists()["shortlists"]
		self.assertEqual([(m["name"], m["item_count"]) for m in mine], [(view["name"], 2)])
		self.assertEqual(result["link"], frappe.utils.get_url(f"/sellos/client/shortlists/{view['name']}"))
		self.assertTrue(result["shortlist"]["shared"])

	def test_sharing_an_empty_shortlist_or_by_another_way_is_refused(self):
		view = self.build()
		_as("agent")
		with self.assertRaises(frappe.ValidationError):
			shortlists.share_shortlist(view["name"])
		shortlists.add_to_shortlist("Unit", self.units["S101"], shortlist=view["name"])
		with self.assertRaises(frappe.ValidationError):
			shortlists.share_shortlist(view["name"], "Post")

	def test_the_client_is_emailed_the_link_only_when_mail_is_ready(self):
		view = self.build(("Unit", self.units["S101"]))
		result, sent = self.share(view, mail=False)
		self.assertEqual((result["client_has_email"], result["emailed"], sent), (True, False, []))
		result, sent = self.share(view, mail=True)
		self.assertTrue(result["emailed"])
		self.assertEqual(sent[0]["recipients"], [self.client_user])
		self.assertIn(result["link"], sent[0]["message"])
		self.assertNotIn(OTHER_PHONE[-10:], sent[0]["message"])
		self.assertEqual(shortlists.get_shortlist(view["name"])["share_count"], 2)

	def test_a_pdf_share_attaches_the_pdf(self):
		view = self.build(("Unit", self.units["S101"]))
		result, sent = self.share(view, "PDF", mail=True)
		self.assertEqual(
			result["pdf"], f"/api/method/sellos.inventory.shortlists.shortlist_pdf?name={view['name']}"
		)
		attachment = sent[0]["attachments"][0]
		self.assertEqual(attachment["fname"], f"{view['name']}.pdf")
		self.assertTrue(attachment["fcontent"].startswith(b"%PDF"))

	def test_the_pdf_is_a_pdf_with_the_branding_photos_and_prices(self):
		view = self.build(("Unit", self.units["S101"]), ("Listing", self.listing))
		_as("agent")
		doc = frappe.get_doc("Shortlist", view["name"])
		data = shortlists.pdf_view(doc)
		html = shortlists.shortlist_html(data)
		self.assertIn(data["brand"]["name"], html)
		self.assertIn(inr(8_000_000), html)
		self.assertIn(inr(7_500_000), html)
		self.assertIn("P709 Listing", html)
		self.assertIn("data:image/jpeg;base64,", html)  # the listing's photo
		self.assertEqual(len(data["items"][1]["pictures"]), 1)
		shortlists.shortlist_pdf(view["name"])
		self.assertEqual(
			(frappe.local.response.type, frappe.local.response.filename), ("pdf", f"{view['name']}.pdf")
		)
		self.assertTrue(frappe.local.response.filecontent.startswith(b"%PDF"))

	def test_the_plain_pdf_for_a_machine_without_the_layout_program_is_a_pdf_too(self):
		view = self.build(("Unit", self.units["S101"]))
		_as("agent")
		data = shortlists.pdf_view(frappe.get_doc("Shortlist", view["name"]))
		content = build_shortlist_pdf(data, inr)
		self.assertTrue(content.startswith(b"%PDF"))
		self.assertIn(b"P709 Project", content)
		self.assertIn(b"Rs 80,00,000", content)

	def test_neither_the_link_view_nor_the_pdf_holds_another_clients_data_or_another_phone_number(self):
		own = self.build(("Unit", self.units["S101"]))
		self.share(own)
		other_lead = self.other_lead
		_as("agent")
		other = shortlists.create_shortlist(lead=other_lead)["name"]
		shortlists.add_to_shortlist("Unit", self.units["S102"], shortlist=other)
		shortlists.share_shortlist(other)
		_as("client")
		text = frappe.as_json([shortlists.my_shortlists(), shortlists.my_shortlist(own["name"])])
		html = shortlists.shortlist_html(shortlists.pdf_view(frappe.get_doc("Shortlist", own["name"])))
		for where, found in (("view", text), ("pdf", html)):
			with self.subTest(where=where):
				self.assertNotIn("P709 Other Buyer", found)
				self.assertNotIn(other, found)
				for form in phones.forms(OTHER_PHONE) + phones.forms(phones.in_mobile(7093)):
					self.assertNotIn(form, found)
		self.assertEqual(shortlists.my_shortlist(own["name"])["agent"]["phone"], AGENT_PHONE)
		self.assertIn(AGENT_PHONE, html)


class TestOpenedMarks(ShortlistCase):
	"""SOS-P7-09: the agent sees which items the client opened, and when."""

	def test_an_item_the_client_opens_shows_its_count_and_times_to_the_agent(self):
		view = self.build(("Unit", self.units["S101"]), ("Listing", self.listing))
		first, second = (i["name"] for i in view["items"])
		_as("agent")
		shortlists.share_shortlist(view["name"])
		self.assertEqual(
			[i["opened"] for i in shortlists.get_shortlist(view["name"])["items"]],
			[{"count": 0, "first": "", "last": ""}] * 2,
		)
		_as("client")
		shortlists.my_shortlist(view["name"])  # seeing the list opens no home
		shortlists.open_shortlist_item(view["name"], second)
		shortlists.open_shortlist_item(view["name"], second)
		_as("agent")
		seen = shortlists.get_shortlist(view["name"])
		opened = [i["opened"] for i in seen["items"]]
		self.assertEqual(opened[0]["count"], 0)
		self.assertEqual(opened[1]["count"], 2)
		self.assertTrue(opened[1]["first"] and opened[1]["last"] >= opened[1]["first"])
		self.assertEqual(seen["opened_count"], 1)
		self.assertTrue(seen["client_last_opened_on"])
		self.assertNotEqual(opened[1]["first"], "")
		self.assertEqual(first, seen["items"][0]["name"])

	def test_the_client_view_carries_no_opened_marks(self):
		view = self.build(("Unit", self.units["S101"]))
		_as("agent")
		shortlists.share_shortlist(view["name"])
		_as("client")
		item = shortlists.my_shortlist(view["name"])["items"][0]
		self.assertNotIn("opened", item)

	def test_only_a_shared_shortlist_of_the_client_can_be_opened(self):
		view = self.build(("Unit", self.units["S101"]))
		item = view["items"][0]["name"]
		_as("client")
		with self.assertRaises(frappe.PermissionError):
			shortlists.open_shortlist_item(view["name"], item)  # still a draft
		_as("agent")
		shortlists.share_shortlist(view["name"])
		shortlists.archive_shortlist(view["name"])
		_as("client")
		with self.assertRaises(frappe.PermissionError):
			shortlists.open_shortlist_item(view["name"], item)  # archived: hidden again
		self.assertEqual(shortlists.my_shortlists(), {"shortlists": []})


class TestNoLongerAvailable(ShortlistCase):
	"""SOS-P7-09: an item whose listing is unpublished or whose unit is not Available is marked so."""

	def test_an_unpublished_listing_and_a_held_unit_are_marked_for_the_agent_and_the_client(self):
		view = self.build(
			("Listing", self.listing), ("Unit", self.units["S101"]), ("Unit", self.units["S102"])
		)
		_as("agent")
		shortlists.share_shortlist(view["name"])
		self.assertEqual(
			[i["unavailable"] for i in shortlists.get_shortlist(view["name"])["items"]], [False] * 3
		)
		_as("company_admin")
		listings.unpublish_listing(self.listing)
		api.set_inventory_status("Unit", self.units["S101"], "Held")
		frappe.db.set_value("Unit", self.units["S102"], "status", "Sold")
		_as("agent")
		agent_view = self.items(shortlists.get_shortlist(view["name"]))
		_as("client")
		client_view = self.items(shortlists.my_shortlist(view["name"]))
		for seen in (agent_view, client_view):
			self.assertEqual(
				[(i["unavailable"], i["reason"]) for i in seen.values()],
				[
					(True, "Unpublished"),
					(True, "No longer available (Held)"),
					(True, "No longer available (Sold)"),
				],
			)
		self.assertEqual(len(client_view), 3)  # marked, never removed

	def test_a_listing_of_a_unit_that_is_not_available_is_marked_too(self):
		unit_listing = listings.save_listing(
			{
				"title": "P709 Unit Listing",
				"listing_type": "Primary",
				"unit": self.units["S103"],
				"asking_price": 8_000_000,
				"description": "A unit",
			}
		)["name"]
		listings.publish_listing(unit_listing)
		view = self.build(("Listing", unit_listing))
		self.assertFalse(view["items"][0]["unavailable"])
		api.set_inventory_status("Unit", self.units["S103"], "Held")
		_as("agent")
		item = shortlists.get_shortlist(view["name"])["items"][0]
		self.assertEqual((item["unavailable"], item["reason"]), (True, "No longer available (Held)"))
		self.assertEqual(shortlists.get_shortlist(view["name"])["unavailable_count"], 1)


class TestPermissions(ShortlistCase):
	"""SOS-P7-09: a client sees only their own shortlist, and a user sees only the shortlists they may."""

	def test_a_client_sees_only_the_shortlists_made_for_their_own_record(self):
		own = self.build(("Unit", self.units["S101"]))
		_as("agent")
		other = shortlists.create_shortlist(lead=self.other_lead)["name"]
		shortlists.add_to_shortlist("Unit", self.units["S102"], shortlist=other)
		shortlists.share_shortlist(own["name"])
		shortlists.share_shortlist(other)
		_as("client")
		self.assertEqual([m["name"] for m in shortlists.my_shortlists()["shortlists"]], [own["name"]])
		with self.assertRaises(frappe.PermissionError):
			shortlists.my_shortlist(other)
		with self.assertRaises(frappe.PermissionError):
			shortlists.open_shortlist_item(other, frappe.get_doc("Shortlist", other).items[0].name)
		with self.assertRaises(frappe.PermissionError):
			shortlists.my_shortlist("SL-99999")  # missing reads like another client's

	def test_a_client_has_none_of_the_agents_methods_and_no_direct_read(self):
		view = self.build(("Unit", self.units["S101"]))
		_as("client")
		for call in (
			lambda: shortlists.get_shortlist(view["name"]),
			lambda: shortlists.list_shortlists(),
			lambda: shortlists.create_shortlist(lead=self.lead),
			lambda: shortlists.share_shortlist(view["name"]),
			lambda: shortlists.shortlist_pdf(view["name"]),
		):
			with self.assertRaises(frappe.PermissionError):
				call()
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list("Shortlist")

	def test_an_agent_and_a_partner_use_no_client_method(self):
		for who in ("agent", "company_admin", "channel_partner"):
			_as(who)
			with self.subTest(who=who), self.assertRaises(frappe.PermissionError):
				shortlists.my_shortlists()

	def test_an_agent_reads_only_their_own_shortlists(self):
		mine = self.build(("Unit", self.units["S101"]))
		_as("company_admin")
		theirs = shortlists.create_shortlist(lead=self.lead)["name"]
		_as("agent")
		self.assertEqual([s["name"] for s in shortlists.list_shortlists()["shortlists"]], [mine["name"]])
		with self.assertRaises(frappe.PermissionError):
			shortlists.get_shortlist(theirs)
		with self.assertRaises(frappe.PermissionError):
			shortlists.add_to_shortlist("Unit", self.units["S101"], shortlist=theirs)
		_as("company_admin")
		self.assertEqual(len(shortlists.list_shortlists()["shortlists"]), 2)

	def test_a_sales_manager_reads_its_teams_shortlists_and_changes_none(self):
		view = self.build(("Unit", self.units["S101"]))
		_as("sales_manager")
		self.assertEqual(shortlists.list_shortlists(), {"shortlists": []})  # no team yet
		with self.assertRaises(frappe.PermissionError):
			shortlists.get_shortlist(view["name"])
		_as("company_admin")
		frappe.get_doc(
			{
				"doctype": "Sales Team",
				"team_name": "P709 Team",
				"manager": self.manager,
				"members": [{"agent": self.agent}],
			}
		).insert()
		_as("sales_manager")
		self.assertEqual(shortlists.get_shortlist(view["name"])["name"], view["name"])
		self.assertFalse(shortlists.get_shortlist(view["name"])["can_edit"])
		with self.assertRaises(frappe.PermissionError):
			shortlists.update_shortlist(view["name"], title="x")

	def test_an_agent_makes_a_shortlist_only_for_a_client_they_may_see(self):
		_as("company_admin")
		hidden = crm.save_client(
			values={"client_name": "P709 Hidden", "client_type": "Buyer", "phone": phones.in_mobile(7095)}
		)["name"]
		_as("agent")
		with self.assertRaises(frappe.PermissionError):
			shortlists.create_shortlist(client=hidden)


class TestRegressionSeed(ShortlistCase):
	"""SOS-P7-09: the regression data holds a shared shortlist and a draft for Regression Buyer One, and the spec
	helpers make and clean up what the Cypress spec reads."""

	def test_the_seed_makes_the_shortlists_and_is_safe_to_run_again(self):
		from sellos.tests import ui_fixtures

		agent = TEST_USERS["agent"]["email"]
		_as("agent")
		buyer = crm.save_client(
			values={
				"client_name": f"{ui_fixtures.REGRESSION_PREFIX}Buyer One",
				"client_type": "Buyer",
				"phone": phones.in_mobile(7096),
			}
		)["name"]
		self.make_lead(buyer, agent)
		_as("company_admin")
		ui_fixtures._seed_pricing(frappe.session.user, agent)
		ui_fixtures._seed_listings(frappe.session.user, agent)
		ui_fixtures._seed_listing_media(agent)
		ui_fixtures._seed_shortlists(agent)
		ui_fixtures._seed_shortlists(agent)
		rows = frappe.get_all(
			"Shortlist", filters={"client": buyer}, fields=["name", "title", "shared_on"], order_by="creation"
		)
		self.assertEqual(
			[(r.title, bool(r.shared_on)) for r in rows],
			[("Regression Shortlist", True), ("Regression Draft Shortlist", False)],
		)
		self.assertEqual(frappe.db.get_value("Client", buyer, "email"), self.client_user)
		_as("client")
		mine = shortlists.my_shortlists()["shortlists"]
		self.assertEqual([m["title"] for m in mine if m["name"] == rows[0].name], ["Regression Shortlist"])
		self.assertNotIn(rows[1].name, [m["name"] for m in mine])
		items = shortlists.my_shortlist(rows[0].name)["items"]
		self.assertEqual(
			[(i["kind"], i["note"], len(i["photos"])) for i in items],
			[("Unit", "Corner flat, park facing", 2), ("Listing", "", 2)],
		)


class TestSpecHelpers(IntegrationTestCase):
	"""SOS-P7-09: the spec helpers make and read back a buyer for the client user and clean up. The helpers commit,
	so this case makes nothing of its own beforehand."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def test_the_spec_helpers_make_and_read_back_a_buyer_for_the_client_and_clean_up(self):
		from sellos.tests import ui_fixtures

		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(ui_fixtures.remove_seeded_leads)
		self.addCleanup(ui_fixtures.remove_gate_inventory)
		self.addCleanup(ui_fixtures.remove_gate_shortlists)
		made = ui_fixtures.make_gate_shortlists()
		self.assertEqual(made["client_email"], TEST_USERS["client"]["email"])
		self.assertEqual(
			frappe.db.get_value("User", TEST_USERS["agent"]["email"], "mobile_no"), made["agent_phone"]
		)
		client = frappe.db.get_value("Lead", made["agent_lead"], "client")
		self.assertEqual(frappe.db.get_value("Client", client, "email"), TEST_USERS["client"]["email"])
		_as("agent")
		shortlists.add_to_shortlist("Unit", made["units"]["M101"], lead=made["agent_lead"])
		ui_fixtures.set_gate_unit_status(made["units"]["M101"], "Held")
		ui_fixtures.set_gate_listing_published(made["listing"], 0)
		self.assertEqual(frappe.db.get_value("Unit", made["units"]["M101"], "status"), "Held")
		self.assertEqual(frappe.db.get_value("Listing", made["listing"], "published"), 0)
		ui_fixtures.remove_gate_shortlists()
		self.assertEqual(frappe.db.count("Shortlist", {"client": client}), 0)
		self.assertFalse(frappe.db.get_value("User", TEST_USERS["agent"]["email"], "mobile_no"))
