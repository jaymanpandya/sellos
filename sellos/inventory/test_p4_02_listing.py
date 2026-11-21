"""SOS-P4-02: a listing is typed Primary, Direct or Partner, published only when complete, and audited."""

import frappe

from sellos.inventory import api, listings
from sellos.inventory.test_p4_01_inventory import InventoryCase, _as
from sellos.testing.users import TEST_USERS

FULL = {
	"title": "P402 Sea view 2 BHK",
	"listing_type": "Direct",
	"asking_price": 12500000,
	"description": "A bright two bedroom flat with a sea view.",
}


class ListingCase(InventoryCase):
	def make_property(self, title="P402 Flat"):
		return api.save_property(
			{"title": title, "property_type": "Apartment", "city": "Pune", "carpet_area": 700}
		)["name"]

	def make_listing(self, **extra):
		values = {**FULL, **extra}
		if "property" not in values and "unit" not in values:
			values["property"] = self.make_property(f"P402 Flat {frappe.generate_hash(length=5)}")
		return listings.save_listing(values)["name"]

	def make_unit(self, project=None, number="1201", **extra):
		project = project or self.make_project("P402 Tower", rera="P51800040201", developer="P402 Developer")
		return super().make_unit(project, number, **extra)

	def history(self, name):
		return [(c.field_label, c.old_value, c.new_value) for c in frappe.get_doc("Listing", name).changes]


class TestCreateAndPublish(ListingCase):
	"""SOS-P4-02: an end to end create and publish, each listing with a type."""

	def test_a_listing_is_made_a_draft_published_and_withdrawn(self):
		name = self.make_listing()
		doc = frappe.get_doc("Listing", name)
		self.assertEqual((doc.listing_type, doc.published, doc.archived), ("Direct", 0, 0))

		result = listings.publish_listing(name)
		doc.reload()
		self.assertEqual((doc.published, doc.published_by), (1, TEST_USERS["company_admin"]["email"]))
		self.assertTrue(doc.published_on)
		shown = next(r for r in result["listings"] if r["name"] == name)
		self.assertEqual((shown["published"], shown["listing_type"], shown["missing"]), (1, "Direct", []))

		listings.unpublish_listing(name)
		doc.reload()
		self.assertEqual((doc.published, doc.published_on, doc.published_by), (0, None, None))

	def test_a_primary_listing_is_of_a_unit_and_each_type_is_kept(self):
		unit = self.make_unit()
		primary = self.make_listing(listing_type="Primary", unit=unit)
		partner = self.make_listing(listing_type="Partner")
		self.assertEqual(frappe.db.get_value("Listing", primary, "listing_type"), "Primary")
		self.assertEqual(frappe.db.get_value("Listing", partner, "listing_type"), "Partner")
		listings.publish_listing(primary)
		self.assertEqual(frappe.db.get_value("Listing", primary, "published"), 1)

	def test_a_type_outside_the_three_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_listing(listing_type="Rental")

	def test_a_primary_listing_of_a_property_and_a_listing_of_both_are_refused(self):
		prop = self.make_property()
		unit = self.make_unit()
		with self.assertRaises(frappe.ValidationError):
			listings.save_listing({**FULL, "listing_type": "Primary", "property": prop})
		with self.assertRaises(frappe.ValidationError):
			listings.save_listing({**FULL, "unit": unit, "property": prop})

	def test_one_unit_is_listed_once(self):
		unit = self.make_unit()
		self.make_listing(listing_type="Primary", unit=unit)
		with self.assertRaises(frappe.ValidationError):
			self.make_listing(listing_type="Primary", unit=unit, title="P402 Again")

	def test_save_listing_never_publishes(self):
		prop = self.make_property()
		name = listings.save_listing({**FULL, "property": prop, "published": 1})["name"]
		self.assertEqual(frappe.db.get_value("Listing", name, "published"), 0)


class TestIncompleteCannotPublish(ListingCase):
	"""SOS-P4-02: publishing needs the required fields; an incomplete listing cannot be published."""

	def test_a_draft_missing_a_required_field_is_refused_and_says_which(self):
		for field, words in (
			("asking_price", "asking price"),
			("description", "description"),
			("property", "unit or a property"),
		):
			values = {**FULL, "property": self.make_property(f"P402 Flat {field}")}
			values["title"] = f"P402 Missing {field}"
			values.pop(field)
			name = listings.save_listing(values)["name"]
			with self.subTest(field=field), self.assertRaises(frappe.ValidationError) as caught:
				listings.publish_listing(name)
			self.assertIn(words, str(caught.exception))
			self.assertEqual(frappe.db.get_value("Listing", name, "published"), 0)

	def test_a_zero_price_or_blank_description_is_incomplete(self):
		name = self.make_listing()
		listings.save_listing({"asking_price": 0, "description": "  "}, name)
		self.assertEqual(
			frappe.get_doc("Listing", name).missing_for_publish(), ["an asking price", "a description"]
		)
		with self.assertRaises(frappe.ValidationError):
			listings.publish_listing(name)

	def test_the_check_holds_for_any_save_not_only_the_api(self):
		doc = frappe.get_doc({"doctype": "Listing", "title": "P402 Direct", "listing_type": "Direct"})
		doc.published = 1
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_editing_a_published_listing_cannot_leave_it_incomplete(self):
		name = self.make_listing()
		listings.publish_listing(name)
		with self.assertRaises(frappe.ValidationError):
			listings.save_listing({"description": ""}, name)

	def test_a_sold_or_archived_target_cannot_be_published(self):
		name = self.make_listing()
		prop = frappe.db.get_value("Listing", name, "property")
		api.set_inventory_status("Property", prop, "Sold")
		with self.assertRaises(frappe.ValidationError):
			listings.publish_listing(name)
		api.set_inventory_status("Property", prop, "Available")
		api.set_inventory_archived("Property", prop, 1)
		with self.assertRaises(frappe.ValidationError):
			listings.publish_listing(name)


class TestAudit(ListingCase):
	"""SOS-P4-02: every change to a listing is logged with who made it and when."""

	def test_each_change_is_logged_with_its_before_and_after(self):
		name = self.make_listing()
		first = self.history(name)
		self.assertIn(("Title", "", FULL["title"]), first)
		self.assertIn(("Type", "", "Direct"), first)
		self.assertNotIn("Published", [f for f, _o, _n in first])

		listings.save_listing({"asking_price": 13000000, "listing_type": "Partner"}, name)
		listings.publish_listing(name)
		rows = self.history(name)[len(first) :]
		self.assertEqual(
			rows,
			[
				("Type", "Direct", "Partner"),
				("Asking price", "12500000", "13000000"),
				("Published", "No", "Yes"),
			],
		)
		for change in frappe.get_doc("Listing", name).changes:
			self.assertEqual(change.changed_by, TEST_USERS["company_admin"]["email"])
			self.assertTrue(change.changed_on)

	def test_the_change_is_logged_whichever_way_it_is_saved_and_by_whom(self):
		name = self.make_listing()
		_as("agent")
		doc = frappe.get_doc("Listing", name)
		doc.title = "P402 Renamed"
		doc.save()
		last = frappe.get_doc("Listing", name).changes[-1]
		self.assertEqual(
			(last.field_label, last.old_value, last.new_value, last.changed_by),
			("Title", FULL["title"], "P402 Renamed", TEST_USERS["agent"]["email"]),
		)

	def test_a_save_that_changes_nothing_adds_no_row(self):
		name = self.make_listing()
		count = len(self.history(name))
		listings.save_listing({"title": FULL["title"]}, name)
		self.assertEqual(len(self.history(name)), count)

	def test_the_change_history_is_returned_to_the_app(self):
		name = self.make_listing()
		listings.publish_listing(name)
		shown = next(r for r in listings.listing_overview()["listings"] if r["name"] == name)
		self.assertEqual(shown["changes"][-1]["what"], "Published")
		self.assertEqual(shown["changes"][-1]["new"], "Yes")
		self.assertTrue(shown["changes"][-1]["changed_by_name"])

	def test_version_tracking_is_on(self):
		self.assertEqual(frappe.get_meta("Listing").track_changes, 1)


class TestArchiveAndRoles(ListingCase):
	"""SOS-P4-02: a listing is archived, never deleted, and only permitted roles edit."""

	def test_archiving_unpublishes_and_a_delete_is_refused(self):
		name = self.make_listing()
		listings.publish_listing(name)
		listings.set_listing_archived(name, 1)
		doc = frappe.get_doc("Listing", name)
		self.assertEqual((doc.archived, doc.published), (1, 0))
		self.assertEqual(doc.changes[-1].field_label, "Archived")
		with self.assertRaises(frappe.ValidationError):
			listings.publish_listing(name)
		self.assertNotIn(name, [r["name"] for r in listings.listing_overview()["listings"]])
		self.assertIn(name, [r["name"] for r in listings.listing_overview(1)["listings"]])
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Listing", name)

	def test_an_agent_edits_and_a_sales_manager_only_reads(self):
		name = self.make_listing()
		_as("agent")
		listings.publish_listing(name)
		self.assertTrue(listings.listing_overview()["can_edit"])
		with self.assertRaises(frappe.PermissionError):
			listings.set_listing_archived(name)
		_as("sales_manager")
		self.assertFalse(listings.listing_overview()["can_edit"])
		for call in (
			lambda: listings.save_listing({"title": "P402 No"}, name),
			lambda: listings.unpublish_listing(name),
		):
			with self.assertRaises(frappe.PermissionError):
				call()

	def test_a_client_a_partner_and_the_platform_admin_see_none(self):
		for who in ("client", "channel_partner", "platform_admin"):
			_as(who)
			with self.subTest(who=who), self.assertRaises(frappe.PermissionError):
				listings.listing_overview()


class TestRegressionSeed(ListingCase):
	"""SOS-P4-02: the regression data holds a Primary and a Direct listing, published, and a Partner draft."""

	def test_the_seed_makes_the_listings_and_is_safe_to_run_again(self):
		from sellos.tests import ui_fixtures

		agent = TEST_USERS["agent"]["email"]
		ui_fixtures._seed_pricing(frappe.session.user, agent)
		ui_fixtures._seed_listings(frappe.session.user, agent)
		ui_fixtures._seed_listings(frappe.session.user, agent)
		rows = frappe.get_all(
			"Listing",
			filters={"title": ["like", "Regression %"]},
			fields=["title", "listing_type", "published", "asking_price"],
			order_by="title asc",
		)
		self.assertEqual(
			[(r.title, r.listing_type, r.published, r.asking_price) for r in rows],
			[
				("Regression Direct Resale", "Direct", 1, 8200000),
				("Regression Partner Draft", "Partner", 0, 0),
				("Regression Primary 2 BHK", "Primary", 1, 10500000),
			],
		)
