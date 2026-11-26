"""SOS-LOOP: electronic signing of a mandate through DocuSeal, against a fake DocuSeal server on this machine.
Settings and secrets, send for signing, the webhook (valid, invalid secret, replayed, out of order, oversized, rate
limited), the signed copy and audit trail, and the files DocuSeal may point at."""

import io
import json
from unittest.mock import patch

import frappe
from pypdf import PdfReader
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from sellos.access import webhooks
from sellos.crm.test_crm import as_user
from sellos.inventory import docuseal, docuseal_webhook, mandates
from sellos.inventory.mandates import is_released
from sellos.inventory.test_p4_05_mandate import MandateCase
from sellos.tests.fake_docuseal import (
	COMPANY_SUBMITTER,
	KEY,
	SELLER_SUBMITTER,
	SUBMISSION_ID,
	WEBHOOK_SECRET,
	FakeDocuSeal,
)

METHOD = "sellos.inventory.docuseal_webhook.docuseal_event"
PATH = f"/api/method/{METHOD}"
BASE = "https://tenant.example"
SELLER_EMAIL = "loop.seller@example.com"
SIGNER_EMAIL = "loop.signer@example.com"


def post(payload=None, body=None, secret=WEBHOOK_SECRET, headers=None):
	"""Call the webhook as DocuSeal does: a JSON post with the company's secret header, as a guest."""
	body = body if body is not None else json.dumps(payload).encode()
	sent = {"Content-Type": "application/json", **(headers or {})}
	if secret:
		sent["X-Webhook-Secret"] = secret
	environ = EnvironBuilder(method="POST", path=PATH, base_url=BASE, data=body, headers=sent)
	frappe.local.request = Request(environ.get_environ())
	frappe.local.response = frappe._dict()
	frappe.set_user("Guest")
	try:
		answer = docuseal_webhook.docuseal_event()
	finally:
		frappe.set_user("Administrator")
	return answer, frappe.local.response.get("http_status_code")


def event(kind, data, at="2026-11-26T10:00:00Z"):
	return {"event_type": kind, "timestamp": at, "data": data}


class SigningCase(MandateCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.fake = FakeDocuSeal().start()
		self.addCleanup(self.fake.stop)
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.cache.delete_keys("sellos_webhook_rate")

	def connect(self, signer=True):
		doc = frappe.get_doc("SellOS Settings")
		doc.update(
			{
				"docuseal_url": self.fake.url,
				"docuseal_api_key": KEY,
				"docuseal_webhook_secret": WEBHOOK_SECRET,
				"docuseal_signer_name": "Asha Pandya" if signer else "",
				"docuseal_signer_email": SIGNER_EMAIL if signer else "",
			}
		)
		doc.save(ignore_permissions=True)

	def seller_mandate(self, email=SELLER_EMAIL):
		lead = self.agent_seller("Signer Owner")
		client = frappe.db.get_value("Lead", lead, "client")
		frappe.db.set_value("Client", client, "email", email)
		return lead, self.mandate(lead)

	def sent_mandate(self):
		self.connect()
		lead, name = self.seller_mandate()
		as_user("agent")
		docuseal.send_for_signing(name)
		return lead, name

	def doc(self, name):
		return frappe.get_doc("Mandate", name)

	def writes(self):
		return {d: frappe.db.count(d) for d in ("Mandate", "File", "Webhook Event", "Version")}

	def done_events(self, name):
		"""Every signer has signed and the submission has completed, as DocuSeal reports it."""
		return event(
			"submission.completed",
			{
				"id": SUBMISSION_ID,
				"status": "completed",
				"audit_log_url": f"{self.fake.url}/files/audit.pdf",
				"documents": [{"name": "mandate", "url": f"{self.fake.url}/files/signed.pdf"}],
			},
		)


class TestDocusealSettings(SigningCase):
	def test_the_key_and_secret_are_saved_encrypted_and_never_returned(self):
		as_user("company_admin")
		saved = docuseal.save_docuseal_settings(
			{
				"url": self.fake.url,
				"api_key": KEY,
				"webhook_secret": WEBHOOK_SECRET,
				"signer_name": "Asha Pandya",
				"signer_email": SIGNER_EMAIL,
			}
		)
		self.assertEqual(
			(saved["has_api_key"], saved["has_webhook_secret"], saved["connected"]), (True, True, True)
		)
		self.assertNotIn(KEY, json.dumps(saved))
		self.assertNotIn(WEBHOOK_SECRET, json.dumps(saved))
		self.assertNotIn(KEY, json.dumps(docuseal.get_docuseal_settings()))
		self.assertTrue(saved["webhook_url"].endswith(f"/api/method/{METHOD}"))
		# Stored in the encrypted table, not as plain text in the settings row.
		self.assertNotEqual(frappe.db.get_single_value("SellOS Settings", "docuseal_api_key"), KEY)
		self.assertEqual(frappe.get_doc("SellOS Settings").get_password("docuseal_api_key"), KEY)

	def test_a_blank_key_keeps_the_one_saved(self):
		self.connect()
		as_user("company_admin")
		saved = docuseal.save_docuseal_settings({"api_key": "", "signer_name": "Someone Else"})
		self.assertTrue(saved["has_api_key"])
		self.assertEqual(frappe.get_doc("SellOS Settings").get_password("docuseal_api_key"), KEY)
		self.assertEqual(saved["signer_name"], "Someone Else")

	def test_a_bad_address_or_signer_email_is_refused(self):
		as_user("company_admin")
		for bad in (
			{"url": "http://sign.example.com"},
			{"url": "https://user:pass@sign.example.com"},
			{"url": "javascript:alert(1)"},
			{"url": "ftp://sign.example.com"},
			{"url": "https://sign.example.com?x=1"},
			{"signer_email": "not an email"},
		):
			with self.assertRaises(frappe.ValidationError, msg=str(bad)):
				docuseal.save_docuseal_settings(bad)

	def test_the_status_says_when_docuseal_is_not_connected(self):
		as_user("company_admin")
		self.assertEqual(
			docuseal.docuseal_status(), {"connected": False, "settings_path": "/company/settings"}
		)
		self.connect()
		self.assertTrue(docuseal.docuseal_status()["connected"])

	def test_the_connection_test_reaches_the_fake_server_with_the_key(self):
		self.connect()
		as_user("company_admin")
		self.assertEqual(docuseal.check_docuseal_connection(), {"ok": 1})
		self.assertEqual(self.fake.requests[-1][3], KEY)
		frappe.db.set_single_value("SellOS Settings", "docuseal_url", "http://127.0.0.1:9")
		with self.assertRaises(frappe.ValidationError):
			docuseal.check_docuseal_connection()

	def test_only_the_right_roles_hold_the_methods(self):
		for who in ("sales_manager", "channel_partner", "client", "platform_admin"):
			as_user(who)
			for call in (docuseal.docuseal_status, docuseal.get_docuseal_settings):
				with self.assertRaises(frappe.PermissionError, msg=f"{who} {call.__name__}"):
					call()
		as_user("agent")
		with self.assertRaises(frappe.PermissionError):
			docuseal.get_docuseal_settings()
		with self.assertRaises(frappe.PermissionError):
			docuseal.save_docuseal_settings({"signer_name": "x"})
		self.assertIn("connected", docuseal.docuseal_status())


class TestSendForSigning(SigningCase):
	def test_not_connected_the_mandate_is_not_sent(self):
		_lead, name = self.seller_mandate()
		as_user("agent")
		with self.assertRaisesRegex(frappe.ValidationError, "Connect DocuSeal"):
			docuseal.send_for_signing(name)
		self.assertEqual(self.fake.requests, [])

	def test_it_needs_the_sellers_email_and_the_companys_signer(self):
		self.connect(signer=False)
		lead, name = self.seller_mandate()
		as_user("agent")
		with self.assertRaisesRegex(frappe.ValidationError, "company's signer"):
			docuseal.send_for_signing(name)
		self.connect()
		frappe.db.set_value("Client", frappe.db.get_value("Lead", lead, "client"), "email", "")
		with self.assertRaisesRegex(frappe.ValidationError, "seller's email"):
			docuseal.send_for_signing(name)
		self.assertEqual(self.fake.requests, [])

	def test_it_sends_the_branded_document_to_both_signers_and_records_where_it_stands(self):
		_lead, name = self.sent_mandate()
		template, submission = (
			self.fake.posts("/api/templates/pdf")[0],
			self.fake.posts("/api/submissions")[0],
		)
		# The document, with a signature field per role on the page that holds it.
		fields = template["documents"][0]["fields"]
		self.assertEqual({f["role"] for f in fields}, {"Seller", "Company"})
		for f in fields:
			area = f["areas"][0]
			self.assertEqual(f["type"], "signature")
			self.assertTrue(all(0 <= area[k] <= 1 for k in ("x", "y", "w", "h")))
			self.assertGreaterEqual(area["page"], 1)
		import base64

		pdf = base64.b64decode(template["documents"][0]["file"])
		text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
		for word in (
			"Mandate to sell property",
			name,
			"Signer Owner",
			"Exclusive mandate",
			"1.5% of the sale price",
			"Asha Pandya",
		):
			self.assertIn(word, text)
		self.assertEqual(
			[(s["role"], s["email"]) for s in submission["submitters"]],
			[("Seller", SELLER_EMAIL), ("Company", SIGNER_EMAIL)],
		)
		self.assertTrue(submission["send_email"])
		# What the mandate records.
		doc = self.doc(name)
		self.assertEqual(
			(doc.signing_status, doc.signing_provider, doc.docuseal_submission_id, doc.status),
			("Sent", "DocuSeal", str(SUBMISSION_ID), "Draft"),
		)
		self.assertTrue(doc.signing_sent_on)
		self.assertEqual(
			[(s.role, s.status, s.submitter_id) for s in doc.signers],
			[("Seller", "Sent", str(SELLER_SUBMITTER)), ("Company", "Sent", str(COMPANY_SUBMITTER))],
		)
		self.assertTrue(frappe.db.exists("File", {"file_url": doc.mandate_document, "is_private": 1}))
		row = self.row(name)
		self.assertEqual((row["signing_status"], len(row["signers"])), ("Sent", 2))

	def test_the_terms_are_locked_while_it_is_out_and_it_can_not_be_sent_twice(self):
		_lead, name = self.sent_mandate()
		as_user("agent")
		with self.assertRaisesRegex(frappe.ValidationError, "out for signing"):
			mandates.save_mandate({"fee_percent": 3}, name)
		with self.assertRaisesRegex(frappe.ValidationError, "already out for signing"):
			docuseal.send_for_signing(name)

	def test_a_declined_mandate_can_be_changed_and_sent_again(self):
		_lead, name = self.sent_mandate()
		self.assertEqual(
			post(event("form.declined", {"id": SELLER_SUBMITTER, "submission_id": SUBMISSION_ID})),
			("ok", None),
		)
		as_user("agent")
		mandates.save_mandate({"fee_percent": 2}, name)
		docuseal.send_for_signing(name)
		self.assertEqual(self.doc(name).signing_status, "Sent")
		self.assertEqual(len(self.fake.posts("/api/submissions")), 2)

	def test_when_docuseal_fails_nothing_is_recorded_and_the_key_is_not_shown(self):
		self.connect()
		_lead, name = self.seller_mandate()
		self.fake.fail = True
		as_user("agent")
		with self.assertRaises(frappe.ValidationError) as caught:
			docuseal.send_for_signing(name)
		self.assertNotIn(KEY, str(caught.exception))
		self.assertEqual(self.doc(name).signing_status, "Not sent")
		self.assertFalse(self.doc(name).signers)

	def test_it_is_refused_for_a_signed_or_foreign_mandate(self):
		self.connect()
		_lead, name = self.seller_mandate()
		self.sign(name)
		as_user("agent")
		with self.assertRaisesRegex(frappe.ValidationError, "already signed"):
			docuseal.send_for_signing(name)
		as_user("sales_manager")
		with self.assertRaises(frappe.PermissionError):
			docuseal.send_for_signing(name)


class TestDocusealWebhook(SigningCase):
	def test_it_is_registered_with_every_check_and_allows_guests(self):
		checks = webhooks.declared_webhooks()[METHOD]
		self.assertEqual(checks["provider"], "docuseal")
		self.assertEqual(checks["secret_setting"], "SellOS Settings.docuseal_webhook_secret")
		for name in ("signature", "replay", "max_body_bytes", "rate_limit_per_tenant"):
			self.assertTrue(checks[name])

	def test_viewed_then_signed_moves_the_statuses_and_the_times(self):
		_lead, name = self.sent_mandate()
		viewed = event(
			"form.viewed", {"id": SELLER_SUBMITTER, "submission_id": SUBMISSION_ID}, "2026-11-26T09:00:00Z"
		)
		self.assertEqual(post(viewed), ("ok", None))
		doc = self.doc(name)
		self.assertEqual(doc.signing_status, "Viewed")
		self.assertEqual([s.status for s in doc.signers], ["Viewed", "Sent"])
		self.assertTrue(doc.signing_viewed_on and doc.signers[0].viewed_on)
		for who in (SELLER_SUBMITTER, COMPANY_SUBMITTER):
			post(
				event(
					"form.completed",
					{"id": who, "submission_id": SUBMISSION_ID},
					f"2026-11-26T1{who - 100}:00:00Z",
				)
			)
		doc = self.doc(name)
		self.assertEqual([s.status for s in doc.signers], ["Signed", "Signed"])
		self.assertEqual(
			(doc.signing_status, doc.status), ("Viewed", "Draft")
		)  # still waiting for the submission

	def test_a_completed_submission_stores_the_signed_pdf_and_trail_and_signs_the_mandate(self):
		_lead, name = self.sent_mandate()
		self.assertEqual(post(self.done_events(name)), ("ok", None))
		doc = self.doc(name)
		self.assertEqual((doc.status, doc.signing_status), ("Signed", "Signed"))
		self.assertTrue(doc.signing_completed_on and doc.signed_on)
		self.assertTrue(is_released(doc))  # signing releases the Dossier
		for url, name_part in ((doc.signed_document, "signed"), (doc.audit_trail, "audit-trail")):
			file = frappe.get_doc("File", {"file_url": url})
			self.assertEqual((file.is_private, name_part in url), (1, True))
		row = self.row(name)
		self.assertEqual(
			(row["signing_status"], row["has_signed_document"], bool(row["audit_trail"])), ("Signed", 1, True)
		)
		self.assertTrue(row["dossier_released"])
		from sellos.inventory.test_p4_05_mandate import can_open

		self.assertTrue(can_open(frappe.get_doc("File", {"file_url": doc.signed_document}), "agent"))
		self.assertFalse(
			can_open(frappe.get_doc("File", {"file_url": doc.signed_document}), "channel_partner")
		)

	def test_a_replayed_event_changes_nothing(self):
		_lead, name = self.sent_mandate()
		body = json.dumps(self.done_events(name)).encode()
		self.assertEqual(post(body=body), ("ok", None))
		first = self.writes()
		self.assertEqual(post(body=body), ("ignored", None))
		self.assertEqual(self.writes(), first)

	def test_an_event_that_arrives_late_is_ignored(self):
		_lead, name = self.sent_mandate()
		post(self.done_events(name))
		before = self.writes()
		late = event(
			"form.viewed", {"id": SELLER_SUBMITTER, "submission_id": SUBMISSION_ID}, "2026-11-26T08:00:00Z"
		)
		self.assertEqual(post(late), ("ignored", None))
		expired = event("submission.expired", {"id": SUBMISSION_ID})
		self.assertEqual(post(expired), ("ignored", None))
		doc = self.doc(name)
		self.assertEqual((doc.signing_status, doc.status), ("Signed", "Signed"))
		self.assertEqual(self.writes()["Mandate"], before["Mandate"])

	def test_declined_and_expired(self):
		_lead, name = self.sent_mandate()
		post(event("form.declined", {"id": COMPANY_SUBMITTER, "submission_id": SUBMISSION_ID}))
		doc = self.doc(name)
		self.assertEqual(
			(doc.signing_status, doc.signers[1].status, bool(doc.signing_declined_on)),
			("Declined", "Declined", True),
		)
		self.assertEqual(doc.status, "Draft")
		again = event("submission.expired", {"id": SUBMISSION_ID})
		self.assertEqual(post(again), ("ignored", None))  # a final status is not left
		_lead2, name2 = self.seller_mandate()
		as_user("agent")
		docuseal.send_for_signing(name2)
		self.fake.requests.clear()
		# The second submission has the same fake id, so address it through its own mandate.
		frappe.db.set_value("Mandate", name2, "docuseal_submission_id", "777")
		post(event("submission.expired", {"id": 777}))
		self.assertEqual(self.doc(name2).signing_status, "Expired")

	def test_an_event_for_no_mandate_or_an_unknown_kind_is_ignored(self):
		_lead, name = self.sent_mandate()
		self.assertEqual(post(event("form.viewed", {"id": 1, "submission_id": 999999})), ("ignored", None))
		self.assertEqual(post(event("template.created", {"id": SUBMISSION_ID})), ("ignored", None))
		self.assertEqual(post(body=b"not json"), ("refused", 403))
		self.assertEqual(self.doc(name).signing_status, "Sent")

	def test_a_wrong_or_missing_secret_writes_nothing_and_reveals_nothing(self):
		_lead, name = self.sent_mandate()
		before = self.writes()
		body = json.dumps(self.done_events(name)).encode()
		answers = {
			post(body=body, secret=""),
			post(body=body, secret="another-secret"),
			post(body=body, secret=WEBHOOK_SECRET + " "),
			post(body=body, secret=None, headers={"X-Auth-Token": KEY}),
		}
		self.assertEqual(answers, {("refused", 403)})
		self.assertEqual(self.writes(), before)
		self.assertEqual(self.doc(name).status, "Draft")

	def test_with_no_secret_saved_every_request_is_refused(self):
		_lead, name = self.sent_mandate()
		frappe.db.delete("__Auth", {"doctype": "SellOS Settings", "fieldname": "docuseal_webhook_secret"})
		self.assertEqual(post(self.done_events(name)), ("refused", 403))

	def test_the_tenant_is_the_site_and_not_a_header(self):
		_lead, _name = self.sent_mandate()
		answer = post(
			event("form.viewed", {"id": SELLER_SUBMITTER, "submission_id": SUBMISSION_ID}),
			headers={"X-Tenant": "other", "Host": "other.example"},
		)
		self.assertEqual(answer, ("ok", None))

	def test_an_oversized_body_is_refused_before_anything_is_written(self):
		before = self.writes()
		big = event("form.viewed", {"id": 1, "pad": "x" * docuseal_webhook.MAX_BODY_BYTES})
		self.assertEqual(post(big), ("too large", 413))
		self.assertEqual(self.writes(), before)

	def test_the_cap_is_checked_from_the_declared_length_before_the_body_is_read(self):
		with patch.object(Request, "get_data", side_effect=AssertionError("body was read")):
			environ = EnvironBuilder(method="POST", path=PATH, base_url=BASE, data=b"{}").get_environ()
			environ["CONTENT_LENGTH"] = str(docuseal_webhook.MAX_BODY_BYTES + 1)
			frappe.local.request = Request(environ)
			frappe.local.response = frappe._dict()
			self.assertEqual(docuseal_webhook.docuseal_event(), "too large")

	def test_requests_over_the_limit_are_refused_and_write_nothing(self):
		with patch("sellos.access.webhooks.time.time", return_value=1_700_000_000):
			for _count in range(docuseal_webhook.REQUESTS_PER_MINUTE):
				self.assertFalse(
					webhooks.over_rate_limit(METHOD, docuseal_webhook.REQUESTS_PER_MINUTE, 1_700_000_000)
				)
			before = self.writes()
			self.assertEqual(post(event("form.viewed", {"id": 1})), ("rate limited", 429))
			self.assertEqual(self.writes(), before)

	def test_the_secret_and_key_appear_nowhere(self):
		_lead, name = self.sent_mandate()
		answers = [post(self.done_events(name)), post(self.done_events(name), secret="wrong")]
		with patch("frappe.logger") as logger:
			post(event("form.viewed", {"id": 1}))
		self.assertFalse(logger.called)
		self.assertNotIn(WEBHOOK_SECRET, repr(answers))
		for doctype in ("Webhook Event", "Mandate", "Version", "Activity Log"):
			rows = json.dumps(frappe.get_all(doctype, fields=["*"], limit=500), default=str)
			self.assertNotIn(WEBHOOK_SECRET, rows, doctype)
			self.assertNotIn(KEY, rows, doctype)

	def test_the_documents_must_be_pdfs_from_the_companys_docuseal_or_a_public_host(self):
		_lead, _name = self.sent_mandate()
		for url in (
			"http://example.com/files/signed.pdf",  # not https
			"https://127.0.0.1/files/signed.pdf",  # a private address that is not the company's DocuSeal
			"file:///etc/passwd",
			"",
		):
			with self.assertRaises(docuseal.DocuSealError, msg=url):
				docuseal.fetch(url)
		self.fake.files["/files/signed.pdf"] = b"<html>not a pdf</html>"
		with self.assertRaises(docuseal.DocuSealError):
			docuseal.fetch(f"{self.fake.url}/files/signed.pdf")
		self.fake.files["/files/signed.pdf"] = b"%PDF-1.4 ok"
		self.assertTrue(docuseal.fetch(f"{self.fake.url}/files/signed.pdf").startswith(b"%PDF"))
		# The key goes to the company's own DocuSeal, as the one fetch above shows.
		self.assertEqual(self.fake.requests[-1][3], KEY)

	def test_a_document_that_can_not_be_fetched_leaves_the_mandate_unchanged(self):
		_lead, name = self.sent_mandate()
		self.fake.files["/files/signed.pdf"] = b"not a pdf"
		with self.assertRaises(docuseal.DocuSealError):
			post(self.done_events(name))
		doc = self.doc(name)
		self.assertEqual((doc.status, doc.signing_status), ("Draft", "Sent"))
