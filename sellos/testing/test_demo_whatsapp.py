"""The demo's WhatsApp content (sellos/testing/demo_whatsapp.py): volumes, formats, determinism. No bench."""

import random
import string
import unittest
from collections import Counter
from datetime import date, datetime

from sellos.testing import demo_ctx, demo_data
from sellos.testing import demo_whatsapp as dw

TODAY = date(2026, 11, 25)
STAGES = [f"Stage {i}" for i in range(11)]
CONSENTS = ("Consented", "Unknown", "Opted out", "Registered DND")


def leads(n=180):
	return [
		{
			"name": f"LEAD-{i:05d}",
			"client_name": f"Person{i} Surname",
			"stage": STAGES[i % 11],
			"consent": CONSENTS[(i // 11) % 4],
		}
		for i in range(n)
	]


PROJECTS = [
	{"name": "Powai Lakeview Heights", "locality": "Powai", "prices": [18_500_000, 24_000_000]},
	{"name": "Thane Greens", "locality": "Thane", "prices": [9_500_000]},
	{"name": "Bopal Orchid", "locality": "Bopal", "prices": []},
]


def plans(word="bom", seed=1):
	return dw.plan(random.Random(seed), word, TODAY, leads(), PROJECTS, f"Pandya Realtors - {word.upper()}")


class TestDemoWhatsApp(unittest.TestCase):
	def test_texts_per_style(self):
		for style in dw.STYLES:
			count = sum(len(group) for group in dw.MESSAGES[style].values()) + len(dw.BOT[style])
			self.assertTrue(25 <= count <= 35, f"{style}: {count} texts")

	def test_no_forbidden_word(self):
		words = (*demo_data.FORBIDDEN_WORDS, "regression")
		everything = [*dw.all_texts(), *dw.HANDOFF_NOTES, *(t[3] for t in dw.TEMPLATES)]
		for text in everything:
			for word in words:
				self.assertNotIn(word, text.lower() + " ", text)
		for plan in plans():
			for _kind, payload in plan["steps"]:
				for word in words:
					self.assertNotIn(word, str(payload).lower() + " ")

	def test_placeholders_resolve(self):
		data = dict.fromkeys(("name", "project", "locality", "price", "time", "agent", "company"), "x")
		for text in dw.all_texts():
			names = {f for _, f, _, _ in string.Formatter().parse(text) if f}
			self.assertLessEqual(names, set(data), text)
			text.format(**data)

	def test_templates(self):
		for word, gujarati in (("bom", 0), ("amd", 2)):
			found = dw.templates_for(word)
			self.assertEqual(sum(1 for t in found if t[1] == "gu"), gujarati)
			self.assertGreaterEqual(len(found), 7)
			for name, language, category, body in found:
				self.assertRegex(name, r"^[a-z0-9_]{1,100}$")
				self.assertIn(language, ("en", "hi", "gu"))
				self.assertIn(category, ("Utility", "Marketing"))
				self.assertIn("{{1}}", body)
				self.assertIn("{{2}}", body)
		names = {t[0] for t in dw.templates_for("amd")}
		for kinds in dw.TEMPLATE_OF.values():
			self.assertLessEqual(set(kinds), names)

	def test_company_name_goes_in_and_placeholders_stay(self):
		"""SOS-LOOP 25 Nov: str.format used to turn {{1}} into {1}, which no message could fill."""
		for _name, _language, _category, body in dw.templates_for("amd"):
			saved = dw.company_body(body, "Pandya Realtors")
			self.assertNotIn("{company}", saved)
			self.assertIn("{{1}}", saved)
			self.assertIn("{{2}}", saved)

	def test_a_sent_template_has_no_placeholder_left(self):
		from sellos.whatsapp.conversations import _render

		for body in ("Hello {{1}}, your visit is at {{2}}.", "Hello {1}, your visit is at {2}."):
			self.assertEqual(_render(body, ["Asha", "11 am"]), "Hello Asha, your visit is at 11 am.")
			shown = _render(body, ["Asha"])
			self.assertNotRegex(shown, r"\{")
			self.assertIn("Asha", shown)

	def test_volume_and_kinds(self):
		for word in ("bom", "amd"):
			found = plans(word)
			self.assertEqual(len(found), sum(dw.KIND_COUNTS.values()))
			self.assertGreaterEqual(len(found), demo_ctx.MINIMUMS["whatsapp_conversations"])
			self.assertEqual(Counter(p["kind"] for p in found), Counter(dw.KIND_COUNTS))
			self.assertEqual(len({p["lead"] for p in found}), len(found))  # a conversation per lead

	def test_spread_and_consent(self):
		by_name = {lead["name"]: lead for lead in leads()}
		found = plans()
		self.assertGreaterEqual(len({by_name[p["lead"]]["stage"] for p in found}), 8)
		for p in found:
			consent = by_name[p["lead"]]["consent"]
			if p["kind"] == "warning":
				self.assertIn(consent, dw.WARNING_STATES)
			if p["kind"] in ("stop", "start"):
				self.assertEqual(consent, "Unknown")

	def test_every_state_is_covered(self):
		for p in plans():
			kinds = [k for k, _ in p["steps"]]
			if p["kind"] == "waiting":
				self.assertEqual(kinds[-1], "in")
			if p["kind"] == "template_only":
				self.assertEqual(kinds, ["template"])
			if p["kind"] == "handoff":
				self.assertEqual(kinds[-1], "handoff")
				self.assertTrue(p["steps"][-1][1])
			if p["kind"] == "closed":
				self.assertEqual(kinds[-1], "close")
			if p["kind"] == "stop":
				self.assertIn(("in", "STOP"), p["steps"])
				self.assertEqual(kinds.count("out"), 2)  # an answer and the one confirmation
				self.assertEqual(kinds[-1], "task")
				self.assertEqual(kinds[kinds.index("task") - 1], "out")
			if p["kind"] == "start":
				self.assertEqual(p["steps"][0], ("in", "START"))
			if p["kind"] in ("chat", "warning"):
				self.assertEqual(kinds[-1], "out")

	def test_times_are_past_ordered_and_one_day(self):
		for p in plans("amd"):
			self.assertEqual(len(p["times"]), len(p["steps"]))
			self.assertEqual(p["times"], sorted(p["times"]))
			self.assertLess(p["times"][-1], datetime.combine(TODAY, datetime.min.time()))
			self.assertEqual(p["times"][0].date(), p["times"][-1].date())

	def test_style_mix_by_region(self):
		amd = Counter(p["style"] for p in plans("amd"))
		bom = Counter(p["style"] for p in plans("bom"))
		self.assertEqual(amd.most_common(1)[0][0], "gujarati")
		self.assertNotIn("marathi", amd)
		self.assertTrue(bom["english"] + bom["hinglish"] > bom["gujarati"] + bom["marathi"])

	def test_only_amd_uses_gujarati_templates(self):
		for p in plans("bom"):
			for kind, payload in p["steps"]:
				if kind == "template":
					self.assertFalse(payload[0].endswith("_gu"))

	def test_template_parameters(self):
		for p in plans():
			for kind, payload in p["steps"]:
				if kind == "template":
					self.assertEqual(len(payload[1]), 2)
					self.assertTrue(all(payload[1]))

	def test_price_text(self):
		self.assertEqual(dw.price_text(18_500_000), "Rs 1.85 crore")
		self.assertEqual(dw.price_text(9_500_000), "Rs 95 lakh")

	def test_deterministic(self):
		self.assertEqual(plans("bom", 5), plans("bom", 5))
		self.assertNotEqual(plans("bom", 5), plans("bom", 6))

	def test_too_few_leads_fail_clearly(self):
		with self.assertRaises(ValueError):
			dw.plan(random.Random(1), "bom", TODAY, leads(10), PROJECTS, "Co")
