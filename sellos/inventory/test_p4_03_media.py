"""SOS-P4-03: photos and videos link to a listing, invalid files are refused, and the order can be changed."""

import base64
import io
from pathlib import Path

import frappe
from PIL import Image

from sellos.inventory import media
from sellos.inventory.test_p4_01_inventory import _as
from sellos.inventory.test_p4_02_listing import ListingCase


def picture(kind, colour=0, size=(8, 8)):
	"""A real small picture, so the file opens as the kind it claims to be."""
	out = io.BytesIO()
	Image.new("RGB", size, (colour, 0, 0)).save(out, kind)
	return out.getvalue()


JPEG = picture("JPEG")
PNG = picture("PNG")
WEBP = picture("WEBP")
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"video body " * 8
WEBM = b"\x1a\x45\xdf\xa3" + b"webm body " * 8


def b64(content):
	return base64.b64encode(content).decode()


class MediaCase(ListingCase):
	def setUp(self):
		super().setUp()
		before = set(Path(frappe.get_site_path("public", "files")).glob("media-*"))
		self.addCleanup(self.remove_files, before)

	@staticmethod
	def remove_files(before):
		for path in set(Path(frappe.get_site_path("public", "files")).glob("media-*")) - before:
			path.unlink()

	def upload(self, listing, filename="front.jpg", content=JPEG, title="Front view"):
		return media.upload_listing_media(listing, title, filename, b64(content))

	def order(self, listing):
		return [m["title"] for m in media.listing_media(listing)["media"]]


class TestAttach(MediaCase):
	"""SOS-P4-03: valid files attach to a listing and are read back."""

	def test_each_valid_type_is_stored_as_a_file_and_an_asset_on_the_listing(self):
		listing = self.make_listing()
		cases = [
			("a.jpg", JPEG, "Photo", "image/jpeg"),
			("b.PNG", PNG, "Photo", "image/png"),
			("c.webp", WEBP, "Photo", "image/webp"),
			("d.mp4", MP4, "Video", "video/mp4"),
			("e.mov", MP4 + b"mov", "Video", "video/quicktime"),
			("f.webm", WEBM, "Video", "video/webm"),
		]
		for filename, content, _kind, _content_type in cases:
			with self.subTest(filename=filename):
				self.upload(listing, filename, content, f"Title {filename}")
		shown = media.listing_media(listing)["media"]
		self.assertEqual([m["title"] for m in shown], [f"Title {c[0]}" for c in cases])
		self.assertEqual([m["position"] for m in shown], [1, 2, 3, 4, 5, 6])
		for row, (filename, content, kind, content_type) in zip(shown, cases, strict=True):
			asset = frappe.get_doc("Media Asset", row["name"])
			self.assertEqual(
				(asset.media_type, asset.content_type, asset.size_bytes), (kind, content_type, len(content))
			)
			self.assertEqual(asset.file_name, filename)
			stored = frappe.get_doc("File", {"file_url": asset.file})
			self.assertEqual(
				Path(frappe.get_site_path("public", asset.file.lstrip("/"))).read_bytes(), content
			)
			self.assertEqual(
				(stored.is_private, stored.attached_to_doctype, stored.attached_to_name),
				(0, "Media Asset", asset.name),
			)
			self.assertNotIn("front", asset.file)
		self.assertEqual(frappe.get_doc("Listing", listing).media[0].media_asset, shown[0]["name"])

	def test_an_asset_in_the_library_links_to_a_second_listing(self):
		first, second = self.make_listing(), self.make_listing()
		asset = self.upload(first)["media"][0]["name"]
		library = media.listing_media(second)["library"]
		self.assertEqual([(a["name"], a["linked"]) for a in library if a["name"] == asset], [(asset, False)])
		result = media.link_listing_media(second, asset)
		self.assertEqual([m["name"] for m in result["media"]], [asset])
		self.assertTrue(next(a for a in result["library"] if a["name"] == asset)["linked"])
		again = media.link_listing_media(second, asset)  # a second click changes nothing
		self.assertEqual(len(again["media"]), 1)
		self.assertEqual([m["name"] for m in media.listing_media(first)["media"]], [asset])

	def test_taking_a_file_off_keeps_it_in_the_library_and_logs_it(self):
		listing = self.make_listing()
		asset = self.upload(listing)["media"][0]["name"]
		result = media.unlink_listing_media(listing, asset)
		self.assertEqual(result["media"], [])
		self.assertTrue(frappe.db.exists("Media Asset", asset))
		self.assertIn(asset, [a["name"] for a in result["library"]])
		history = [(c[0], c[2]) for c in self.history(listing)]
		self.assertIn(("Media", "Added Front view"), history)
		self.assertIn(("Media", "Removed Front view"), history)

	def test_a_media_asset_can_not_be_deleted(self):
		asset = self.upload(self.make_listing())["media"][0]["name"]
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Media Asset", asset)

	def test_an_archived_listing_takes_no_media(self):
		from sellos.inventory import listings

		listing = self.make_listing()
		listings.set_listing_archived(listing)
		with self.assertRaises(frappe.ValidationError):
			self.upload(listing)

	def test_a_listing_takes_up_to_the_limit(self):
		listing = self.make_listing()
		for n in range(media.MAX_PER_LISTING):
			frappe.get_doc(
				{
					"doctype": "Media Asset",
					"title": f"P403 Bulk {n}",
					"media_type": "Photo",
					"file": f"/files/p403-bulk-{n}.jpg",
				}
			).insert()
		names = frappe.get_all("Media Asset", filters={"title": ["like", "P403 Bulk %"]}, pluck="name")
		for name in names:
			media.link_listing_media(listing, name)
		with self.assertRaises(frappe.ValidationError):
			self.upload(listing)


class TestInvalidFiles(MediaCase):
	"""SOS-P4-03: an invalid file is refused, and nothing is stored."""

	def refused(self, listing, filename, content, text):
		before = (frappe.db.count("Media Asset"), frappe.db.count("File"))
		with self.assertRaises(frappe.ValidationError) as caught:
			self.upload(listing, filename, content)
		self.assertIn(text, str(caught.exception))
		self.assertEqual((frappe.db.count("Media Asset"), frappe.db.count("File")), before)
		self.assertEqual(media.listing_media(listing)["media"], [])

	def test_a_type_that_is_not_a_photo_or_a_video_is_refused(self):
		listing = self.make_listing()
		for filename in ("brochure.pdf", "run.exe", "page.html", "noextension", "photo.jpg.exe", "anim.gif"):
			with self.subTest(filename=filename):
				self.refused(listing, filename, JPEG, "must be a")

	def test_a_file_whose_bytes_are_not_its_type_is_refused(self):
		listing = self.make_listing()
		self.refused(listing, "fake.jpg", b"<html><script>alert(1)</script></html>", "not a real")
		self.refused(listing, "fake.png", JPEG, "not a real")
		self.refused(listing, "fake.mp4", PNG, "not a real")
		self.refused(listing, "fake.webm", MP4, "not a real")

	def test_a_picture_that_does_not_open_is_refused(self):
		self.refused(self.make_listing(), "cut.jpg", JPEG[:4] + b"not a picture " * 8, "can not be read")

	def test_an_empty_file_is_refused(self):
		self.refused(self.make_listing(), "empty.jpg", b"", "empty")

	def test_a_photo_over_5_mb_and_a_video_over_20_mb_are_refused(self):
		listing = self.make_listing()
		self.refused(listing, "big.jpg", JPEG + b"x" * media.PHOTO_LIMIT, "up to 5 MB")
		self.refused(listing, "big.mp4", MP4 + b"x" * media.VIDEO_LIMIT, "up to 20 MB")

	def test_a_photo_at_the_limit_is_taken(self):
		listing = self.make_listing()
		content = JPEG + b"x" * (media.PHOTO_LIMIT - len(JPEG))
		self.assertEqual(len(self.upload(listing, "edge.jpg", content)["media"]), 1)

	def test_bytes_that_are_not_base64_are_refused(self):
		with self.assertRaises(frappe.ValidationError):
			media.upload_listing_media(self.make_listing(), "x", "x.jpg", "not base64 !!")

	def test_an_asset_that_is_not_in_the_library_or_is_archived_can_not_be_linked(self):
		listing = self.make_listing()
		with self.assertRaises(frappe.DoesNotExistError):
			media.link_listing_media(listing, "MED-99999")
		other = self.make_listing()
		asset = self.upload(other)["media"][0]["name"]
		frappe.db.set_value("Media Asset", asset, "archived", 1)
		with self.assertRaises(frappe.ValidationError):
			media.link_listing_media(listing, asset)


class TestOrder(MediaCase):
	"""SOS-P4-03: the order of a listing's files can be changed."""

	def test_files_keep_the_order_they_were_added_in_and_the_order_can_change(self):
		listing = self.make_listing()
		for title in ("One", "Two", "Three"):
			self.upload(listing, f"{title}.jpg", JPEG, title)
		self.assertEqual(self.order(listing), ["One", "Two", "Three"])
		names = {m["title"]: m["name"] for m in media.listing_media(listing)["media"]}

		result = media.reorder_listing_media(listing, [names["Three"], names["One"], names["Two"]])
		self.assertEqual([m["title"] for m in result["media"]], ["Three", "One", "Two"])
		self.assertEqual([m["position"] for m in result["media"]], [1, 2, 3])
		self.assertEqual(self.order(listing), ["Three", "One", "Two"])
		self.assertEqual(frappe.db.count("Listing Media", {"parent": listing}), 3)
		self.assertIn(("Media", "Order changed"), [(c[0], c[2]) for c in self.history(listing)])

	def test_the_order_is_read_back_from_a_fresh_load(self):
		listing = self.make_listing()
		for title in ("A", "B"):
			self.upload(listing, f"{title}.jpg", JPEG, title)
		names = [m["name"] for m in media.listing_media(listing)["media"]]
		media.reorder_listing_media(listing, frappe.as_json(list(reversed(names))))  # a JSON text is read too
		frappe.clear_document_cache("Listing", listing)
		self.assertEqual([r.media_asset for r in frappe.get_doc("Listing", listing).media], names[::-1])

	def test_an_order_that_is_not_each_file_once_is_refused(self):
		listing = self.make_listing()
		for title in ("A", "B"):
			self.upload(listing, f"{title}.jpg", JPEG, title)
		names = [m["name"] for m in media.listing_media(listing)["media"]]
		for bad in ([names[0]], [names[0], names[0]], [*names, "MED-99999"], []):
			with self.subTest(order=bad), self.assertRaises(frappe.ValidationError):
				media.reorder_listing_media(listing, bad)
		self.assertEqual(self.order(listing), ["A", "B"])

	def test_removing_a_file_closes_the_gap(self):
		listing = self.make_listing()
		for title in ("A", "B", "C"):
			self.upload(listing, f"{title}.jpg", JPEG, title)
		names = {m["title"]: m["name"] for m in media.listing_media(listing)["media"]}
		result = media.unlink_listing_media(listing, names["B"])
		self.assertEqual([(m["title"], m["position"]) for m in result["media"]], [("A", 1), ("C", 2)])


class TestWho(MediaCase):
	"""SOS-P4-03: an Agent and a Company Admin change media, a Sales Manager reads, others are refused."""

	def test_an_agent_uploads_and_a_sales_manager_only_reads(self):
		listing = self.make_listing()
		_as("agent")
		self.upload(listing)
		_as("sales_manager")
		shown = media.listing_media(listing)
		self.assertEqual((len(shown["media"]), shown["can_edit"]), (1, False))
		for call in (
			lambda: self.upload(listing),
			lambda: media.link_listing_media(listing, shown["media"][0]["name"]),
			lambda: media.unlink_listing_media(listing, shown["media"][0]["name"]),
			lambda: media.reorder_listing_media(listing, [shown["media"][0]["name"]]),
		):
			with self.assertRaises(frappe.PermissionError):
				call()
		self.assertEqual(self.order(listing), ["Front view"])

	def test_a_client_and_a_channel_partner_get_nothing(self):
		listing = self.make_listing()
		for who in ("client", "channel_partner"):
			_as(who)
			with self.subTest(who=who), self.assertRaises(frappe.PermissionError):
				media.listing_media(listing)
			with self.subTest(who=who, call="upload"), self.assertRaises(frappe.PermissionError):
				self.upload(listing)


class TestRegressionSeed(MediaCase):
	"""SOS-P4-03: the regression data holds two photos on a listing, in order, and one library photo on none."""

	def test_the_seed_makes_the_media_and_is_safe_to_run_again(self):
		from sellos.testing.users import TEST_USERS
		from sellos.tests import ui_fixtures

		agent = TEST_USERS["agent"]["email"]
		ui_fixtures._seed_pricing(frappe.session.user, agent)
		ui_fixtures._seed_listings(frappe.session.user, agent)
		ui_fixtures._seed_listing_media(agent)
		ui_fixtures._seed_listing_media(agent)
		primary = frappe.db.get_value("Listing", {"title": "Regression Primary 2 BHK"}, "name")
		self.assertEqual(self.order(primary), ["Regression Front View", "Regression Living Room"])
		direct = frappe.db.get_value("Listing", {"title": "Regression Direct Resale"}, "name")
		self.assertEqual(self.order(direct), [])
		library = {a["title"]: a["linked"] for a in media.listing_media(direct)["library"]}
		self.assertEqual(library["Regression Floor Plan"], False)
		self.assertEqual(frappe.db.count("Media Asset", {"title": ["like", "Regression %"]}), 3)

	def test_the_spec_helpers_make_and_read_back_media_and_the_cleanup_removes_it(self):
		from sellos.tests import ui_fixtures

		ui_fixtures.remove_gate_inventory()  # what an earlier run left
		made = ui_fixtures.make_gate_media_listing()
		state = ui_fixtures.gate_media_state(made["listing"])
		self.assertEqual(state["media"], [])
		self.assertEqual(state["assets"], 1)
		ui_fixtures.remove_gate_inventory()
		self.assertEqual(frappe.db.count("Media Asset", {"title": ["like", "Gate Inventory %"]}), 0)
		self.assertEqual(frappe.db.count("Listing", {"title": ["like", "Gate Inventory %"]}), 0)
