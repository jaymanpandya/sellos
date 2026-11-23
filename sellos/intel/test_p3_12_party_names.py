"""SOS-P3-12: party names. Visible only to a Company Admin, never searchable, every view logged, kept five
years; a Facebook poster's name and number live only on the draft listing, masked, deleted on rejection."""

import json

import frappe
from frappe.utils import add_years, today

from sellos.access.roles import COMPANY_ADMIN
from sellos.crm.base import mask_phone
from sellos.intel import party_names
from sellos.inventory.test_p4_02_listing import ListingCase
from sellos.testing.users import TEST_USERS
from sellos.tests import phones

PARTY = "Party Name"
LOG = "Party Name Access Log"


class PartyCase(ListingCase):
	def setUp(self):
		super().setUp()
		self.rid = f"P312-{frappe.generate_hash(length=6)}"
		self.buyer = f"Buyer {frappe.generate_hash(length=6)}"
		self.seller = f"Seller {frappe.generate_hash(length=6)}"
		party_names.store_party_names(self.rid, self.buyer, self.seller)

	def call_as(self, key):
		frappe.set_user(TEST_USERS[key]["email"])
		return party_names.get_party_names(self.rid)


class TestPartyNameVisibility(PartyCase):
	"""SOS-P3-12: names are visible only to allowed roles."""

	def test_a_company_admin_sees_the_names(self):
		rows = self.call_as("company_admin")
		self.assertEqual(
			rows, [{"party": "Buyer", "name": self.buyer}, {"party": "Seller", "name": self.seller}]
		)

	def test_every_other_role_is_refused_and_nothing_is_logged(self):
		for key in TEST_USERS:
			if key == "company_admin":
				continue
			with self.subTest(role=key), self.assertRaises(frappe.PermissionError):
				self.call_as(key)
		self.assertEqual(frappe.db.count(LOG, {"source_record_id": self.rid}), 0)

	def test_no_role_may_read_a_party_name_through_the_generic_paths(self):
		meta = frappe.get_meta(PARTY)
		# The one System Manager row grants no right: without it a newer Frappe adds a System Manager row
		# with write, delete and export.
		self.assertLessEqual({p.role for p in meta.permissions}, {"System Manager"})
		self.assertFalse(
			any(p.read or p.write or p.create or p.delete or p.export or p.share for p in meta.permissions)
		)
		for key in TEST_USERS:
			frappe.set_user(TEST_USERS[key]["email"])
			self.assertFalse(frappe.has_permission(PARTY, "read"), key)
			with self.assertRaises(frappe.PermissionError):
				frappe.get_list(PARTY, fields=["party_name"])

	def test_the_method_is_for_company_admins_only(self):
		from sellos.access.registry import allowed_roles

		self.assertEqual(
			allowed_roles("sellos.intel.party_names.get_party_names"), frozenset({COMPANY_ADMIN})
		)


class TestPartyNameSearch(PartyCase):
	"""SOS-P3-12: name search is off."""

	def test_no_field_can_be_searched_filtered_or_listed(self):
		meta = frappe.get_meta(PARTY)
		self.assertFalse(meta.search_fields)
		for df in meta.fields:
			with self.subTest(field=df.fieldname):
				self.assertFalse(df.search_index or df.in_standard_filter or df.in_list_view)
				self.assertFalse(df.in_global_search)
		self.assertFalse(meta.title_field)

	def test_a_company_admin_cannot_search_for_a_name(self):
		frappe.set_user(TEST_USERS["company_admin"]["email"])
		self.assertEqual(party_names.get_party_names(self.buyer), [])  # a name is not a record id
		from frappe.desk.search import search_link

		with self.assertRaises(frappe.PermissionError):
			search_link(PARTY, self.buyer[:6])


class TestPartyNameAccessLog(PartyCase):
	"""SOS-P3-12: access is logged."""

	def test_every_view_is_logged_without_the_names(self):
		self.call_as("company_admin")
		self.call_as("company_admin")
		rows = frappe.get_all(LOG, filters={"source_record_id": self.rid}, fields=["*"])
		self.assertEqual(len(rows), 2)
		for row in rows:
			self.assertEqual((row.viewer, row.names_shown), (TEST_USERS["company_admin"]["email"], 2))
			self.assertTrue(row.viewed_on)
			self.assertNotIn(self.buyer, json.dumps(row, default=str))
			self.assertNotIn(self.seller, json.dumps(row, default=str))

	def test_a_log_row_is_never_changed_or_deleted(self):
		self.call_as("company_admin")
		frappe.set_user("Administrator")
		doc = frappe.get_doc(LOG, frappe.get_all(LOG, filters={"source_record_id": self.rid})[0].name)
		doc.names_shown = 9
		with self.assertRaises(frappe.ValidationError):
			doc.save()
		with self.assertRaises(frappe.ValidationError):
			doc.delete()


class TestPartyNameRetention(PartyCase):
	"""SOS-P3-12: retention is five years."""

	def test_a_name_is_kept_five_years_then_purged(self):
		row = frappe.get_all(PARTY, filters={"source_record_id": self.rid}, fields=["name", "retain_until"])[
			0
		]
		self.assertEqual(str(row.retain_until), str(add_years(today(), 5)))
		party_names.purge_expired()
		self.assertEqual(frappe.db.count(PARTY, {"source_record_id": self.rid}), 2)
		frappe.db.set_value(PARTY, row.name, "retain_until", frappe.utils.add_days(today(), -1))
		self.assertGreaterEqual(party_names.purge_expired(), 1)
		self.assertEqual(frappe.db.count(PARTY, {"source_record_id": self.rid}), 1)

	def test_the_purge_is_scheduled_daily_and_storing_twice_adds_nothing(self):
		from sellos import hooks

		self.assertIn("sellos.intel.party_names.purge_expired", hooks.scheduler_events["daily"])
		self.assertEqual(party_names.store_party_names(self.rid, self.buyer, self.seller), 0)


class TestPosterDetails(ListingCase):
	"""SOS-P3-12: a poster's details live only on the draft listing, masked, deleted on rejection."""

	def make_draft(self):
		number = phones.in_mobile(312)
		name = self.make_listing()
		doc = frappe.get_doc("Listing", name)
		doc.poster_name = "Poster  Person"
		doc.poster_phone = number
		doc.save()
		return name, number

	def test_the_draft_keeps_the_name_and_a_masked_number(self):
		name, number = self.make_draft()
		doc = frappe.get_doc("Listing", name)
		self.assertEqual((doc.poster_name, doc.poster_phone_masked), ("Poster Person", mask_phone(number)))
		self.assertNotIn(number[-6:], doc.poster_phone_masked)
		fields = {df.fieldname: df.permlevel for df in frappe.get_meta("Listing").fields}
		self.assertEqual(fields["poster_phone"], 1)
		self.assertEqual(fields["poster_phone_masked"], 0)

	def test_only_a_company_admin_may_read_the_full_number(self):
		name, number = self.make_draft()
		for key, sees in (("company_admin", True), ("agent", False), ("sales_manager", False)):
			frappe.set_user(TEST_USERS[key]["email"])
			doc = frappe.get_doc("Listing", name)
			doc.apply_fieldlevel_read_permissions()
			self.assertEqual(doc.get("poster_phone") == number, sees, key)
			self.assertEqual(doc.poster_phone_masked, mask_phone(number))

	def test_rejecting_the_draft_deletes_the_details_everywhere(self):
		name, number = self.make_draft()
		doc = frappe.get_doc("Listing", name)
		doc.rejected = 1
		doc.save()
		doc.reload()
		self.assertEqual((doc.poster_name, doc.poster_phone, doc.poster_phone_masked), (None,) * 3)
		self.assertTrue(doc.rejected_on)
		dump = json.dumps(frappe.get_all("Version", filters={"docname": name}, fields=["data"]))
		self.assertNotIn(number, dump)
		self.assertNotIn("Poster Person", dump)

	def test_publishing_deletes_the_details_too(self):
		from sellos.inventory import listings

		name, _number = self.make_draft()
		listings.publish_listing(name)
		doc = frappe.get_doc("Listing", name)
		self.assertEqual((doc.poster_name, doc.poster_phone), (None, None))
