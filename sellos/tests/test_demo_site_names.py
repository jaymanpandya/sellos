"""SOS-LOOP (demo rebuild, 25 November 2026): the old demo site names and company names are gone from the repository.

The demo company sites are sellos_tenant_demobom.localhost (Pandya Realtors - BOM, Mumbai) and
sellos_tenant_demoamd.localhost (Pandya Realtors - AMD, Ahmedabad), beside sellos_tenant_democontrol.localhost. The
first demo sites had other names; they were rebuilt, not renamed. This test reads every text file of the repository
and fails if one of the old site names, the old company names or the old sign in words is still written in it. The
words are built from pieces below so this file does not contain them either.
"""

import os
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OLD_SITE_NAMES = ("demo" + "alpha", "demo" + "beta")
OLD_COMPANY_NAMES = ("Sky" + "line Realty", "Green" + "field Homes")
OLD_SIGN_IN_WORDS = ("admin.sky" + "line@", "admin.green" + "field@")
SKIP_FOLDERS = {".git", "node_modules", "__pycache__", "public", "screenshots", "ui-reference", ".claude"}
TEXT_SUFFIXES = {
	".py",
	".md",
	".js",
	".vue",
	".json",
	".sh",
	".yml",
	".yaml",
	".txt",
	".html",
	".css",
	".toml",
	".csv",
}


def repository_files():
	for folder, folders, files in os.walk(REPO_ROOT):
		folders[:] = [name for name in folders if name not in SKIP_FOLDERS]
		for name in files:
			path = Path(folder) / name
			if path.suffix in TEXT_SUFFIXES:
				yield path


class TestOldDemoNamesAreGone(unittest.TestCase):
	"""SOS-LOOP demo rebuild: no old demo site or company name anywhere."""

	def found(self, words):
		hits = []
		for path in repository_files():
			text = path.read_text(encoding="utf-8", errors="ignore")
			for word in words:
				if word in text:
					hits.append(f"{path.relative_to(REPO_ROOT)}: {word}")
		return hits

	def test_no_old_site_name_appears_in_the_repository(self):
		self.assertEqual(
			self.found(OLD_SITE_NAMES), [], "The demo sites are demobom, demoamd and democontrol."
		)

	def test_no_old_company_name_or_sign_in_appears_in_the_repository(self):
		self.assertEqual(
			self.found(OLD_COMPANY_NAMES + OLD_SIGN_IN_WORDS),
			[],
			"The demo companies are Pandya Realtors - BOM and Pandya Realtors - AMD.",
		)


if __name__ == "__main__":
	unittest.main()
