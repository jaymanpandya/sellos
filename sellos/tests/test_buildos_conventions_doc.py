"""SOS-P0-01: docs/buildos-conventions.md summarises the BuildOS conventions.

* The summary has sections for structure, tooling, build, frontend, testing and styling.
* The summary lists the changes Frappe 16 and SellOS need, and asks for Jayman's approval.
* The five spot check claims are listed, and each one cites a BuildOS file.
* When the read only reference copy is present, the cited files exist in it.
"""

import re
import unittest
from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / "docs" / "buildos-conventions.md"
REFERENCE = Path.home() / "iespl-baseline" / "buildos-reference"


class TestBuildosConventionsDoc(unittest.TestCase):
	"""SOS-P0-01 conventions summary."""

	@classmethod
	def setUpClass(cls):
		cls.text = DOC.read_text()

	def test_covers_required_topics(self):
		headings = [h.lower() for h in re.findall(r"^## .*$", self.text, re.M)]
		for topic in ("layout", "tooling", "deployment", "frontend", "styling", "testing", "frappe 16"):
			self.assertTrue(any(topic in h for h in headings), f"missing section: {topic}")

	def test_every_section_cites_files(self):
		sections = re.split(r"^## ", self.text, flags=re.M)[1:]
		for section in sections[:9]:
			self.assertRegex(section, r"`[\w./-]+\.[\w]+`", section.splitlines()[0])

	def test_spot_check_and_approval(self):
		spot = self.text.split("## 11. Spot check")[1].split("## 12.")[0]
		claims = re.findall(r"^\d+\. .*$", spot, re.M)
		self.assertEqual(len(claims), 5)
		for claim in claims:
			self.assertRegex(claim, r"`[\w./-]+`")
		self.assertIn("Jayman approves", self.text.split("## 12. Approval")[1])

	def test_cited_files_exist_in_reference(self):
		if not REFERENCE.is_dir():
			self.skipTest("reference copy not present")
		for path in ("buildos/hooks.py", ".github/workflows/ci.yml", "frontend/package.json", ".gitignore"):
			self.assertTrue((REFERENCE / path).is_file(), path)
			self.assertIn(path, self.text)
