"""SOS-P0-03: CLAUDE.md in the repository root and in frontend/.

* Both files exist (SellOS is one app repository, so "every repository" means these two).
* The root file lists build, test and lint commands, the role model, the Frappe 16
  conventions, the link to the build plan and the stop and ask rules.
* The frontend file points back to the root file and lists its own commands.
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestClaudeMdFiles(unittest.TestCase):
	"""SOS-P0-03 conventions files."""

	@classmethod
	def setUpClass(cls):
		cls.root = (ROOT / "CLAUDE.md").read_text()
		cls.frontend = (ROOT / "frontend" / "CLAUDE.md").read_text()

	def test_both_files_exist(self):
		self.assertTrue((ROOT / "CLAUDE.md").is_file())
		self.assertTrue((ROOT / "frontend" / "CLAUDE.md").is_file())

	def test_root_lists_build_test_and_lint_commands(self):
		for command in (
			"npm run build",
			"bench build --app sellos",
			"run-tests --app sellos",
			"pre-commit run --all-files",
		):
			self.assertIn(command, self.root)

	def test_root_states_when_to_stop_and_ask(self):
		self.assertIn("## Stop and ask Jayman when", self.root)
		for trigger in ("secret", "ambiguous", "permissions", "blocked"):
			self.assertIn(trigger, self.root)

	def test_root_has_role_model_conventions_and_plan_link(self):
		self.assertIn("## Frappe 16 conventions", self.root)
		self.assertIn("## Role model", self.root)
		for role in ("Platform Admin", "Company Admin", "Agent", "Client", "Channel Partner"):
			self.assertIn(role, self.root)
		self.assertIn("TASKS.md", self.root)
		self.assertIn("frontend/CLAUDE.md", self.root)

	def test_frontend_file_links_back_and_lists_commands(self):
		self.assertIn("root `CLAUDE.md`", self.frontend)
		self.assertIn("npm run build", self.frontend)
		self.assertIn("Stop and ask Jayman", self.frontend)
