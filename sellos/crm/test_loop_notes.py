"""SOS-LOOP: notes on a lead, a seller and a mandate. The managed types, Other and its label, attachments with
their limits, the permission matrix per record, who edits and removes, and the log of a removal."""

import base64
import io
import zipfile

import frappe
from PIL import Image

from sellos.access.matrix import MATRIX
from sellos.access.roles import AGENT, COMPANY_ADMIN, SALES_MANAGER
from sellos.access.test_p1_18_sales_teams import SalesTeamCase
from sellos.crm import api, notes
from sellos.testing.users import TEST_USERS
from sellos.tests import phones
from sellos.tests.files import tiny_pdf


def b64(content: bytes) -> str:
	return base64.b64encode(content).decode()


def png() -> bytes:
	out = io.BytesIO()
	Image.new("RGB", (8, 8), (30, 120, 60)).save(out, "PNG")
	return out.getvalue()


def office(extra=None) -> bytes:
	out = io.BytesIO()
	with zipfile.ZipFile(out, "w") as z:
		z.writestr("[Content_Types].xml", "<Types/>")
		for name in extra or []:
			z.writestr(name, b"x")
	return out.getvalue()


def file_of(name, content):
	return {"filename": name, "content_base64": b64(content)}


class NoteCase(SalesTeamCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.types = {t["label"]: t["name"] for t in notes._types(only_shown=False)}
		self.addCleanup(frappe.set_user, "Administrator")

	def as_(self, email):
		frappe.set_user(email)

	def add(self, lead, label="Call", body="Spoke to the owner.", **extra):
		return notes.add_note(self.types[label], body, lead=lead, **extra)

	def seller(self, label, assigned_to):
		self.as_(self.admin)
		client = api.save_client(
			values={"client_name": label, "client_type": "Seller", "phone": phones.in_mobile(120)}
		)
		return api.save_lead(
			values={
				"client": client["name"],
				"source": "Website",
				"pipeline": "Seller",
				"assigned_to": assigned_to,
			}
		)["lead"]["name"]


class TestNoteTypes(NoteCase):
	def test_the_ten_starting_types_exist_in_order(self):
		self.assertEqual(
			list(self.types),
			[
				"Call",
				"Site visit",
				"Owner requirement",
				"Price discussion",
				"Legal and title",
				"Inspection",
				"Photos",
				"Document",
				"Follow up",
				"Other",
			],
		)

	def test_other_needs_a_short_label_and_the_others_drop_it(self):
		self.as_(self.manager_a)
		with self.assertRaises(frappe.ValidationError):
			self.add(self.lead_a, "Other")
		with self.assertRaises(frappe.ValidationError):
			self.add(self.lead_a, "Other", custom_label="x" * 41)
		note = self.add(self.lead_a, "Other", custom_label="Parking")["notes"][0]
		self.assertEqual((note["type_label"], note["custom_label"]), ("Parking", "Parking"))
		plain = self.add(self.lead_a, "Call", custom_label="ignored")["notes"][0]
		self.assertEqual((plain["type_label"], plain["custom_label"]), ("Call", ""))

	def test_the_company_renames_adds_and_hides_types(self):
		self.as_(self.admin)
		renamed = notes.save_note_type("Site inspection", name=self.types["Inspection"])["types"]
		self.assertIn("Site inspection", [t["label"] for t in renamed])
		added = notes.save_note_type("Valuation")
		self.assertEqual(added["types"][-1]["label"], "Valuation")
		notes.save_note_type("Photos", name=self.types["Photos"], enabled=0)
		self.assertNotIn("Photos", [t["label"] for t in notes.note_types()["types"]])
		self.assertIn("Photos", [t["label"] for t in notes.note_type_settings()["types"]])
		with self.assertRaises(frappe.ValidationError):
			notes.save_note_type("Other", name=self.types["Other"], enabled=0)
		with self.assertRaises(frappe.ValidationError):
			notes.save_note_type("valuation")
		self.as_(self.manager_a)
		with self.assertRaises(frappe.ValidationError):  # a hidden type is not offered for a new note
			self.add(self.lead_a, "Photos")
		with self.assertRaises(frappe.PermissionError):
			notes.save_note_type("Mine")

	def test_a_hidden_type_keeps_its_old_notes(self):
		self.as_(self.manager_a)
		self.add(self.lead_a, "Photos", "Front view")
		self.as_(self.admin)
		notes.save_note_type("Photos", name=self.types["Photos"], enabled=0)
		self.assertEqual(notes.list_notes(lead=self.lead_a)["notes"][0]["type_label"], "Photos")


class TestNotePermissions(NoteCase):
	def test_a_note_is_read_by_those_who_read_its_lead(self):
		self.as_(self.manager_a)
		name = self.add(self.lead_a)["name"]
		for who, sees in (
			(self.manager_a, True),
			(self.admin, True),
			(self.agent_a, True),
			(self.agent_b, False),
		):
			self.as_(who)
			if sees:
				self.assertEqual(
					[n["name"] for n in notes.list_notes(lead=self.lead_a)["notes"]], [name], who
				)
			else:
				with self.assertRaises(frappe.PermissionError, msg=who):
					notes.list_notes(lead=self.lead_a)
		self.as_(self.manager_b)  # the other team's manager
		with self.assertRaises(frappe.PermissionError):
			notes.list_notes(lead=self.lead_a)
		with self.assertRaises(frappe.PermissionError):
			self.add(self.lead_a)

	def test_a_client_a_partner_and_the_platform_admin_hold_no_note_method(self):
		for key in ("channel_partner", "client", "platform_admin"):
			self.as_(TEST_USERS[key]["email"])
			with self.assertRaises(frappe.PermissionError, msg=key):
				notes.list_notes(lead=self.lead_a)
			with self.assertRaises(frappe.PermissionError, msg=key):
				self.add(self.lead_a)
		for method in ("note_types", "list_notes", "add_note", "update_note", "delete_note"):
			self.assertEqual(
				MATRIX[f"sellos.crm.notes.{method}"], frozenset({COMPANY_ADMIN, AGENT, SALES_MANAGER}), method
			)
		for method in ("note_type_settings", "save_note_type"):
			self.assertEqual(MATRIX[f"sellos.crm.notes.{method}"], frozenset({COMPANY_ADMIN}), method)

	def test_only_the_author_and_a_company_admin_edit_or_remove(self):
		self.as_(self.agent_a)
		mine = self.add(self.lead_a, body="Agent note")["name"]
		self.as_(self.manager_a)
		with self.assertRaises(frappe.PermissionError):
			notes.update_note(mine, self.types["Call"], "Edited by the manager")
		with self.assertRaises(frappe.PermissionError):
			notes.delete_note(mine)
		self.as_(self.agent_a)
		edited = notes.update_note(mine, self.types["Follow up"], "Agent note, edited")["notes"][0]
		self.assertEqual(
			(edited["body"], edited["type_label"], edited["edited"]), ("Agent note, edited", "Follow up", 1)
		)
		self.as_(self.admin)
		notes.update_note(mine, self.types["Call"], "Admin touched it")
		self.as_(self.manager_a)
		own = self.add(self.lead_a, body="Manager note")["name"]
		self.as_(self.agent_a)
		with self.assertRaises(frappe.PermissionError):
			notes.delete_note(own)

	def test_a_removal_hides_the_note_and_is_logged_and_nothing_is_deleted(self):
		self.as_(self.agent_a)
		name = self.add(self.lead_a)["name"]
		self.assertEqual(notes.delete_note(name)["notes"], [])
		doc = frappe.get_doc("Record Note", name)
		self.assertEqual((doc.removed, doc.removed_by), (1, self.agent_a))
		self.assertTrue(doc.removed_on)
		self.assertTrue(frappe.db.exists("Version", {"ref_doctype": "Record Note", "docname": name}))
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Record Note", name)
		self.assertTrue(frappe.db.exists("Record Note", name))
		with self.assertRaises(frappe.ValidationError):  # a removed note is not changed
			notes.update_note(name, self.types["Call"], "back again")

	def test_a_mandates_note_is_read_only_by_those_who_read_the_mandate(self):
		seller = self.seller("LOOP Note Seller", self.agent_a)
		self.as_(self.admin)
		mandate = frappe.get_doc(
			{
				"doctype": "Mandate",
				"lead": seller,
				"mandate_type": "Exclusive",
				"term_months": 6,
				"fee_percent": 1,
			}
		).insert()
		self.add(seller, "Legal and title", "Title is clear", mandate=mandate.name)
		self.add(seller, "Call", "Plain lead note")
		self.assertEqual(len(notes.list_notes(lead=seller)["notes"]), 2)
		self.assertEqual(len(notes.list_notes(mandate=mandate.name)["notes"]), 1)
		self.as_(self.manager_a)  # may read the lead, not the mandate
		self.assertEqual([n["body"] for n in notes.list_notes(lead=seller)["notes"]], ["Plain lead note"])
		with self.assertRaises(frappe.PermissionError):
			notes.list_notes(mandate=mandate.name)
		with self.assertRaises(frappe.PermissionError):
			self.add(seller, mandate=mandate.name)

	def test_notes_can_be_filtered_by_type(self):
		self.as_(self.manager_a)
		self.add(self.lead_a, "Call", "one")
		self.add(self.lead_a, "Inspection", "two")
		rows = notes.list_notes(lead=self.lead_a, note_type=self.types["Inspection"])["notes"]
		self.assertEqual([n["body"] for n in rows], ["two"])


class TestNoteAttachments(NoteCase):
	def test_an_image_and_a_pdf_are_stored_privately_and_opened_by_who_reads_the_note(self):
		self.as_(self.manager_a)
		note = self.add(
			self.lead_a, "Photos", "", files=[file_of("front.png", png()), file_of("deed.pdf", tiny_pdf())]
		)["notes"][0]
		self.assertEqual(
			[(a["file_name"], a["kind"]) for a in note["attachments"]],
			[("front.png", "Image"), ("deed.pdf", "Document")],
		)
		file = frappe.get_doc("File", {"file_url": note["attachments"][0]["file"]})
		self.assertEqual(file.is_private, 1)
		self.assertTrue(file.file_url.startswith("/private/files/"))
		self.as_(self.agent_a)
		self.assertTrue(frappe.has_permission("File", "read", doc=file))
		self.as_(self.agent_b)
		self.assertFalse(frappe.has_permission("File", "read", doc=file))
		self.as_(TEST_USERS["channel_partner"]["email"])
		self.assertFalse(frappe.has_permission("File", "read", doc=file))

	def test_unsafe_or_mismatched_files_are_refused_and_nothing_is_stored(self):
		self.as_(self.manager_a)
		before = frappe.db.count("Record Note")
		bad = {
			"script.exe": b"MZ\x90\x00",
			"page.html": b"<html><script>alert(1)</script></html>",
			"logo.svg": b"<svg onload=alert(1)></svg>",
			"fake.png": b"not a png at all",
			"fake.pdf": b"not a pdf",
			"old.doc": b"\xd0\xcf\x11\xe0",
			"macro.docx": office(["word/vbaProject.bin"]),
			"notes.txt": b"abc\x00def",
			"empty.pdf": b"",
		}
		for name, content in bad.items():
			with self.assertRaises(frappe.ValidationError, msg=name):
				self.add(self.lead_a, "Document", "x", files=[file_of(name, content)])
		self.assertEqual(frappe.db.count("Record Note"), before)

	def test_good_office_and_text_files_pass(self):
		self.as_(self.manager_a)
		files = [
			file_of("sheet.xlsx", office(["xl/workbook.xml"])),
			file_of("a.txt", b"hello"),
			file_of("b.csv", b"a,b\n1,2"),
		]
		note = self.add(self.lead_a, "Document", "", files=files)["notes"][0]
		self.assertEqual(len(note["attachments"]), 3)

	def test_size_and_count_limits(self):
		self.as_(self.manager_a)
		with self.assertRaises(frappe.ValidationError):
			notes.check_attachment("big.pdf", b"%PDF" + b"0" * notes.FILE_LIMIT)
		six = [file_of(f"{n}.txt", b"hello") for n in range(6)]
		with self.assertRaises(frappe.ValidationError):
			self.add(self.lead_a, "Document", "x", files=six)

	def test_a_path_in_the_name_is_dropped(self):
		self.as_(self.manager_a)
		note = self.add(self.lead_a, "Document", "", files=[file_of("../../etc/passwd.txt", b"x")])["notes"][
			0
		]
		self.assertEqual(note["attachments"][0]["file_name"], "passwd.txt")

	def test_a_note_needs_text_or_a_file(self):
		self.as_(self.manager_a)
		with self.assertRaises(frappe.ValidationError):
			self.add(self.lead_a, "Call", "  ")
