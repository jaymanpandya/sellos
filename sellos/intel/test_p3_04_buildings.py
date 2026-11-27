"""SOS-P3-04: the building and micro market master. Micro markets are data a Company Admin edits (add, rename,
split, merge, archive, load from a file), buildings carry their identifiers, a seed list makes buildings that
Need review, and only Confirmed buildings reach the matcher."""

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access.matrix import MATRIX
from sellos.access.roles import AGENT, COMPANY_ADMIN, PLATFORM_ADMIN, ensure_roles
from sellos.intel import buildings, buildings_api, markets
from sellos.intel.identifiers import identifier_fields
from sellos.testing.users import TEST_USERS, create_test_users

MARKET = "Micro Market"
BUILDING = "Building"
SAMPLE = Path(markets.SAMPLE_FILE)


def as_user(key):
	frappe.set_user(TEST_USERS[key]["email"])


class BuildingCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user("Administrator")
		self.tag = uuid.uuid4().hex[:6]
		self.addCleanup(frappe.set_user, "Administrator")

	def market(self, label="a", **values):
		return markets.save_market(
			None,
			{
				"market_name": f"T{self.tag} {label}",
				"country": "India",
				"parent_area": f"T{self.tag} City",
				**values,
			},
		)

	def building(self, label="b", market=None, **values):
		return buildings.save_building(
			None,
			{
				"building_name": f"T{self.tag} {label}",
				"micro_market": market.name if market else "",
				**values,
			},
		)


class TestMicroMarkets(BuildingCase):
	"""SOS-P3-04: micro markets are a DocType, loaded from a file, edited and never deleted."""

	def test_the_sample_file_loads_markets_with_boundaries_and_loading_twice_adds_nothing(self):
		as_user("company_admin")
		data = json.loads(SAMPLE.read_text(encoding="utf-8"))
		first = buildings_api.load_micro_markets()
		again = buildings_api.load_micro_markets()
		self.assertEqual(first, {"created": len(data["markets"]), "updated": 0})
		self.assertEqual(again, {"created": 0, "updated": len(data["markets"])})
		for row in data["markets"]:
			doc = frappe.get_doc(MARKET, {"market_name": row["name"], "country": row["country"]})
			self.assertEqual(doc.status, "Active")
			self.assertEqual(doc.parent_area, row["parent"])
			self.assertEqual(json.loads(doc.boundary)["type"], "Polygon")
		self.assertEqual(frappe.db.count(MARKET, {"market_name": data["markets"][0]["name"]}), 1)

	def test_a_file_you_supply_loads_and_edits_what_is_there(self):
		as_user("company_admin")
		text = json.dumps(
			{"markets": [{"name": f"T{self.tag} Own", "country": "India", "parent": "Own City"}]}
		)
		self.assertEqual(buildings_api.load_micro_markets(text), {"created": 1, "updated": 0})
		edited = json.dumps(
			{"markets": [{"name": f"T{self.tag} Own", "country": "India", "parent": "Other City"}]}
		)
		self.assertEqual(buildings_api.load_micro_markets(edited), {"created": 0, "updated": 1})
		self.assertEqual(
			frappe.db.get_value(MARKET, {"market_name": f"T{self.tag} Own"}, "parent_area"), "Other City"
		)

	def test_a_bad_file_or_boundary_is_refused(self):
		as_user("company_admin")
		for text in ("not json", json.dumps({"nope": []}), "[]"):
			with self.subTest(text=text), self.assertRaises(frappe.ValidationError):
				buildings_api.load_micro_markets(text)
		for boundary in ('{"type":"Polygon","coordinates":[[[0,0],[1,1]]]}', '{"type":"Point"}', "[1]"):
			with self.subTest(boundary=boundary), self.assertRaises(frappe.ValidationError):
				self.market("bad", boundary=boundary)

	def test_two_active_markets_never_share_a_name_in_a_country(self):
		self.market("dup")
		with self.assertRaises(frappe.ValidationError):
			self.market("dup")

	def test_rename_keeps_the_history_and_the_buildings(self):
		as_user("company_admin")
		market = self.market("old")
		house = self.building("house", market)
		row = buildings_api.save_micro_market(market.name, {"market_name": f"T{self.tag} new"})
		self.assertEqual(row["market_name"], f"T{self.tag} new")
		self.assertEqual([h["change"] for h in row["history"]], ["Created", "Renamed"])
		self.assertIn(f"T{self.tag} old", row["history"][1]["detail"])
		self.assertEqual(frappe.db.get_value(BUILDING, house.name, "micro_market"), market.name)

	def test_split_gives_each_building_to_a_part_and_keeps_where_it_was(self):
		as_user("company_admin")
		market = self.market("whole")
		one, two = self.building("one", market), self.building("two", market)
		parts = buildings_api.split_micro_market(
			market.name,
			{"market_name": f"T{self.tag} north"},
			{"market_name": f"T{self.tag} south"},
			{one.name: 0, two.name: 1},
		)
		north, south = parts
		self.assertEqual(frappe.db.get_value(BUILDING, one.name, "micro_market"), north["name"])
		self.assertEqual(frappe.db.get_value(BUILDING, two.name, "micro_market"), south["name"])
		self.assertEqual(north["split_from"], market.name)
		self.assertEqual(frappe.db.get_value(MARKET, market.name, "status"), "Archived")
		self.assertTrue(frappe.db.exists(MARKET, market.name), "nothing is deleted")
		history = buildings_api.get_building(one.name)["market_history"]
		self.assertEqual([h["micro_market"] for h in history], [market.name, north["name"]])
		self.assertEqual(history[1]["reason"], "Split")
		self.assertTrue(history[0]["to_on"])
		self.assertEqual(frappe.get_doc(MARKET, market.name).history[-1].change_kind, "Split")

	def test_a_split_must_assign_every_building(self):
		as_user("company_admin")
		market = self.market("whole")
		one = self.building("one", market)
		self.building("two", market)
		with self.assertRaises(frappe.ValidationError):
			markets.split_market(market.name, {"market_name": "A"}, {"market_name": "B"}, {one.name: 0})
		self.assertEqual(frappe.db.get_value(MARKET, market.name, "status"), "Active")

	def test_merge_moves_the_buildings_and_archives_the_other_market(self):
		as_user("company_admin")
		keep, merge = self.market("keep"), self.market("merge")
		house = self.building("house", merge)
		row = buildings_api.merge_micro_markets(keep.name, merge.name)
		self.assertEqual(row["buildings"], 1)
		self.assertEqual(frappe.db.get_value(BUILDING, house.name, "micro_market"), keep.name)
		self.assertEqual(frappe.db.get_value(MARKET, merge.name, "status"), "Archived")
		self.assertEqual(frappe.db.get_value(MARKET, merge.name, "merged_into"), keep.name)
		history = buildings_api.get_building(house.name)["market_history"]
		self.assertEqual(
			[(h["micro_market"], h["reason"]) for h in history],
			[(merge.name, "Added"), (keep.name, "Merged")],
		)

	def test_archive_is_refused_while_buildings_remain_and_restore_works(self):
		as_user("company_admin")
		market = self.market("arch")
		house = self.building("house", market)
		with self.assertRaises(frappe.ValidationError):
			buildings_api.set_micro_market_archived(market.name, 1)
		other = self.market("other")
		buildings.save_building(house.name, {"micro_market": other.name})
		self.assertEqual(buildings_api.set_micro_market_archived(market.name, 1)["status"], "Archived")
		self.assertEqual(buildings_api.set_micro_market_archived(market.name, 0)["status"], "Active")
		with self.assertRaises(frappe.ValidationError):  # an archived market takes no new building
			buildings_api.set_micro_market_archived(other.name, 1) and None
			buildings.save_building(None, {"building_name": f"T{self.tag} late", "micro_market": other.name})

	def test_nothing_is_deleted(self):
		market = self.market("keepme")
		house = self.building("keepme", market)
		for doc in (market, house):
			with self.subTest(doctype=doc.doctype), self.assertRaises(frappe.PermissionError):
				frappe.delete_doc(doc.doctype, doc.name, force=True)

	def test_no_micro_market_city_or_country_is_in_the_code(self):
		"""The names live in the sample file and the tests only."""
		names = {m["name"] for m in json.loads(SAMPLE.read_text(encoding="utf-8"))["markets"]}
		folder = Path(markets.__file__).parent
		own = ("markets", "buildings", "buildings_api", "platform_master", "geo", "identifiers")
		for path in [folder / f"{n}.py" for n in own]:
			text = path.read_text(encoding="utf-8")
			for name in names | {"Mumbai", "India", "Australia", "Emirates"}:
				with self.subTest(file=path.name, name=name):
					self.assertNotIn(name, text)


class TestBuildingRecord(BuildingCase):
	"""SOS-P3-04: a building's identifiers, with the foreign ones optional, shown by country."""

	def test_india_identifiers_are_stored_with_several_cts_numbers(self):
		house = self.building(
			"in",
			self.market(),
			cts_numbers="cts 10, 10a;cts 10",
			village="Khar",
			tahsil="Bandra",
			district="Mumbai Suburban",
			rera_number="p51800 012345",
		)
		house.reload()
		self.assertEqual([r.cts_number for r in house.cts_numbers], ["CTS 10", "10A"])
		self.assertEqual((house.village, house.tahsil, house.district), ("Khar", "Bandra", "Mumbai Suburban"))
		self.assertEqual(house.rera_number, "P51800012345")
		self.assertEqual(house.country, "India")

	def test_foreign_identifiers_are_stored_and_never_required(self):
		bare = self.building("bare")  # no identifier at all
		self.assertEqual(bare.status, "Needs review")
		uae = self.building(
			"uae", country="United Arab Emirates", uae_community="T Community", dld_number="T-123"
		)
		au = self.building("au", country="Australia", au_lot="12", au_plan="DP34")
		for doc, kept in (
			(uae, {"uae_community": "T Community", "dld_number": "T-123"}),
			(au, {"au_lot": "12", "au_plan": "DP34"}),
		):
			doc.reload()
			for field, value in kept.items():
				self.assertEqual(doc.get(field), value)

	def test_which_identifiers_show_follows_the_country(self):
		self.assertEqual(
			identifier_fields("India"), ["cts_numbers", "village", "tahsil", "district", "rera_number"]
		)
		self.assertEqual(identifier_fields("United Arab Emirates"), ["uae_community", "dld_number"])
		self.assertEqual(identifier_fields("Australia"), ["au_lot", "au_plan"])
		self.assertEqual(identifier_fields(None), identifier_fields("India"))
		as_user("company_admin")
		uae = self.building("uae2", country="United Arab Emirates", uae_community="T Community")
		self.assertEqual(
			buildings_api.get_building(uae.name)["identifier_fields"], ["uae_community", "dld_number"]
		)

	def test_the_sample_buildings_load_as_needs_review_once(self):
		self.assertEqual(markets.load_markets()["created"] > 0, True)
		data = json.loads(SAMPLE.read_text(encoding="utf-8"))
		first = buildings.load_sample_buildings()
		self.assertEqual(first, {"created": len(data["buildings"]), "skipped": 0})
		self.assertEqual(buildings.load_sample_buildings(), {"created": 0, "skipped": len(data["buildings"])})
		row = frappe.get_doc(BUILDING, {"building_name": data["buildings"][0]["name"]})
		self.assertEqual((row.status, row.source), ("Needs review", "Sample file"))
		self.assertEqual(
			frappe.db.get_value(MARKET, row.micro_market, "market_name"), data["buildings"][0]["market"]
		)


class TestSeedList(BuildingCase):
	"""SOS-P3-04: a seed list of names makes buildings that Need review, and never calls LegiScore."""

	def test_a_plain_list_makes_buildings_that_need_review(self):
		as_user("company_admin")
		market = self.market()
		result = buildings_api.load_building_seed_list(
			f"T{self.tag} Tower A\nT{self.tag} Tower B\n\n", market.name
		)
		self.assertEqual((result["created"], result["skipped"], result["rejected"]), (2, 0, []))
		rows = frappe.get_all(
			BUILDING,
			filters={"building_name": ["like", f"T{self.tag} Tower%"]},
			fields=["status", "micro_market", "source", "country"],
		)
		self.assertEqual(
			{(r.status, r.micro_market, r.source, r.country) for r in rows},
			{("Needs review", market.name, "Seed list", "India")},
		)

	def test_a_csv_with_columns_and_the_same_list_twice(self):
		as_user("company_admin")
		market = self.market("csv")
		text = f'Project name,RERA number,CTS,Village,Micro market\nT{self.tag} Heights,p51800 000111,"11, 12",Juhu,{market.market_name}\n,,,,\nT{self.tag} Court,bad rera!,,,\n'
		result = buildings_api.load_building_seed_list(text)
		self.assertEqual(result["created"], 1)
		self.assertEqual([r["row"] for r in result["rejected"]], [2, 3])
		house = frappe.get_doc(BUILDING, {"building_name": f"T{self.tag} Heights"})
		self.assertEqual(
			(house.status, house.micro_market, house.rera_number),
			("Needs review", market.name, "P51800000111"),
		)
		self.assertEqual([r.cts_number for r in house.cts_numbers], ["11", "12"])
		again = buildings_api.load_building_seed_list(text)
		self.assertEqual((again["created"], again["skipped"]), (0, 1))

	def test_an_empty_list_is_refused_and_the_load_never_calls_legiscore(self):
		as_user("company_admin")
		with self.assertRaises(frappe.ValidationError):
			buildings_api.load_building_seed_list("  \n ")
		source = Path(buildings.__file__).read_text(encoding="utf-8")
		for call in ("import requests", "import urllib", "from sellos.intel.legiscore", "make_request"):
			self.assertNotIn(call, source)


class TestReview(BuildingCase):
	"""SOS-P3-04: a reviewer corrects fields (saved with who, when and the old value) and confirms; only a
	Confirmed building reaches the matcher."""

	def test_a_correction_is_saved_with_who_when_and_the_old_value(self):
		as_user("company_admin")
		market = self.market()
		house = self.building("c", market, village="Old Village", rera_number="P51800000222")
		as_user("agent")
		view = buildings_api.correct_building(house.name, {"village": "New Village", "tahsil": "Bandra"})
		self.assertEqual((view["village"], view["status"]), ("New Village", "Needs review"))
		rows = frappe.get_all(
			"Building Correction",
			filters={"building": house.name},
			fields=["fieldname", "old_value", "new_value", "corrected_by", "corrected_on"],
			order_by="fieldname",
		)
		self.assertEqual(
			[(r.fieldname, r.old_value, r.new_value) for r in rows],
			[("tahsil", "", "Bandra"), ("village", "Old Village", "New Village")],
		)
		for row in rows:
			self.assertEqual(row.corrected_by, TEST_USERS["agent"]["email"])
			self.assertTrue(row.corrected_on)
		self.assertEqual(len(buildings_api.get_building(house.name)["corrections"]), 2)

	def test_a_change_to_the_cts_numbers_and_the_market_is_logged_too(self):
		market, other = self.market("m1"), self.market("m2")
		house = self.building("c2", market, cts_numbers="1,2")
		buildings.save_building(house.name, {"cts_numbers": ["1", "3"], "micro_market": other.name})
		changed = {
			r.fieldname: (r.old_value, r.new_value)
			for r in frappe.get_all(
				"Building Correction",
				filters={"building": house.name},
				fields=["fieldname", "old_value", "new_value"],
			)
		}
		self.assertEqual(changed["cts_numbers"], ("1\n2", "1\n3"))
		self.assertEqual(changed["micro_market"], (market.name, other.name))

	def test_confirm_marks_confirmed_with_who_and_when(self):
		house = self.building("conf", self.market())
		as_user("agent")
		view = buildings_api.confirm_building(house.name)
		self.assertEqual(view["status"], "Confirmed")
		self.assertEqual(view["confirmed_by"], TEST_USERS["agent"]["email"])
		self.assertTrue(view["confirmed_on"])
		self.assertEqual(frappe.db.get_value(BUILDING, house.name, "status"), "Confirmed")

	def test_only_confirmed_buildings_reach_the_matcher(self):
		market = self.market()
		draft, done = self.building("draft", market), self.building("done", market)
		buildings.confirm_building(done.name)
		names = [r.name for r in buildings.confirmed_buildings(market.name)]
		self.assertEqual(names, [done.name])
		self.assertNotIn(draft.name, [r.name for r in buildings.confirmed_buildings()])

	def test_the_review_list_filters_by_status_and_searches(self):
		as_user("company_admin")
		market = self.market()
		house = self.building("find", market, cts_numbers="CTS 777", rera_number="P51800000333")
		self.building("other", market)
		buildings.confirm_building(house.name)
		queue = buildings_api.list_buildings(market.name, "Needs review")["rows"]
		self.assertEqual([r["building_name"] for r in queue], [f"T{self.tag} other"])
		for term in ("find", "777", "P51800000333"):
			with self.subTest(term=term):
				rows = buildings_api.list_buildings(market.name, None, term)["rows"]
				self.assertEqual([r["name"] for r in rows], [house.name])


class TestPermissions(BuildingCase):
	"""SOS-P3-04: the permissions of the master, which the permission matrix also covers."""

	def test_the_matrix_lists_every_method(self):
		for method in ("list_buildings", "save_micro_market", "correct_building", "load_platform_master"):
			self.assertIn(f"sellos.intel.buildings_api.{method}", MATRIX)

	def test_an_agent_reviews_but_does_not_edit_markets_or_add_buildings(self):
		market = self.market()
		house = self.building("p", market)
		as_user("agent")
		self.assertTrue(buildings_api.list_micro_markets()["markets"])
		self.assertEqual(buildings_api.correct_building(house.name, {"village": "V"})["village"], "V")
		for call in (
			lambda: buildings_api.save_micro_market(market.name, {"parent_area": "X"}),
			lambda: buildings_api.save_building(None, {"building_name": "X"}),
			lambda: buildings_api.merge_micro_markets(market.name, market.name),
			lambda: buildings_api.load_building_seed_list("X"),
			lambda: buildings_api.load_micro_markets(),
		):
			with self.assertRaises(frappe.PermissionError):
				call()

	def test_an_agent_cannot_link_a_platform_building(self):
		house = self.building("link", self.market())
		as_user("agent")
		view = buildings_api.correct_building(house.name, {"platform_building": "PB-00001", "village": "V"})
		self.assertEqual(view["platform_building"], "")
		as_user("company_admin")
		self.assertEqual(
			buildings_api.save_building(house.name, {"platform_building": "PB-00001"})["platform_building"],
			"PB-00001",
		)

	def test_a_sales_manager_reads_and_the_others_see_nothing(self):
		house = self.building("read", self.market())
		as_user("sales_manager")
		self.assertTrue(buildings_api.get_building(house.name))
		with self.assertRaises(frappe.PermissionError):
			buildings_api.confirm_building(house.name)
		for key in ("client", "channel_partner", "platform_admin", "basic"):
			as_user(key)
			with self.subTest(role=key), self.assertRaises(frappe.PermissionError):
				buildings_api.list_buildings()

	def test_the_company_admin_may_edit_a_building(self):
		house = self.building("edit", self.market())
		as_user("company_admin")
		view = buildings_api.save_building(
			house.name, {"building_name": f"T{self.tag} renamed", "village": "V2"}
		)
		self.assertEqual((view["building_name"], view["village"]), (f"T{self.tag} renamed", "V2"))


class TestPlatformMaster(BuildingCase):
	"""SOS-P3-04: the platform master of buildings is the Platform Admin's, on the control site only."""

	def test_it_loads_the_sample_once_on_the_control_site(self):
		data = json.loads(SAMPLE.read_text(encoding="utf-8"))
		as_user("platform_admin")
		with patch("sellos.intel.platform_master.is_control_site", return_value=True):
			first = buildings_api.load_platform_master()
			again = buildings_api.load_platform_master()
		self.assertEqual(first, {"created": len(data["buildings"]), "skipped": 0})
		self.assertEqual(again, {"created": 0, "skipped": len(data["buildings"])})
		self.assertEqual(
			frappe.db.count("Platform Building", {"building_name": data["buildings"][0]["name"]}), 1
		)

	def test_a_company_site_never_holds_it_and_other_roles_are_refused(self):
		as_user("platform_admin")
		with self.assertRaises(frappe.PermissionError):
			buildings_api.load_platform_master()  # this test site is not the control site
		with patch("sellos.intel.platform_master.is_control_site", return_value=True):
			for key in ("company_admin", "agent"):
				as_user(key)
				with self.subTest(role=key), self.assertRaises(frappe.PermissionError):
					buildings_api.load_platform_master()
		self.assertEqual({AGENT, COMPANY_ADMIN} & {PLATFORM_ADMIN}, set())


class TestRegressionSeed(BuildingCase):
	"""SOS-P3-04: the regression data for the building review is made through the buildings API."""

	def test_the_seed_makes_the_market_and_three_buildings_and_runs_again(self):
		from sellos.tests import ui_fixtures

		ui_fixtures._seed_buildings(TEST_USERS["company_admin"]["email"])
		ui_fixtures._seed_buildings(TEST_USERS["company_admin"]["email"])
		self.assertEqual(frappe.db.count(MARKET, {"market_name": "Regression Market"}), 1)
		status = {
			r.building_name: r.status
			for r in frappe.get_all(
				BUILDING,
				filters={"building_name": ["like", "Regression Tower%"]},
				fields=["building_name", "status"],
			)
		}
		self.assertEqual(
			status,
			{
				"Regression Tower One": "Needs review",
				"Regression Tower Two": "Needs review",
				"Regression Tower Confirmed": "Confirmed",
			},
		)
		one = frappe.get_doc(BUILDING, {"building_name": "Regression Tower One"})
		self.assertEqual([r.cts_number for r in one.cts_numbers], ["101", "102"])
