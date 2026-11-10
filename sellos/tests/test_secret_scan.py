"""SOS-P0-09: a committed secret is blocked before the commit and in continuous integration."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestSecretScan(unittest.TestCase):
	"""SOS-P0-09: the gitleaks scan is wired into pre-commit and the Linters workflow."""

	def test_gitleaks_runs_before_commits(self):
		config = (ROOT / ".pre-commit-config.yaml").read_text()
		self.assertIn("https://github.com/gitleaks/gitleaks", config)
		self.assertIn("id: gitleaks", config)
		self.assertIn("default_stages: [pre-commit]", config)

	def test_gitleaks_runs_in_continuous_integration(self):
		"""The Linters workflow runs every pre-commit hook, gitleaks included, on push and pull request."""
		lint = (ROOT / ".github/workflows/linter.yml").read_text()
		self.assertIn("pre-commit/action", lint)
		self.assertRegex(lint, r"(?m)^  pull_request:\s*$")
		self.assertNotIn("continue-on-error", lint)
		self.assertNotIn("SKIP:", lint)

	def test_secrets_files_are_ignored_by_git(self):
		ignore = (ROOT / ".gitignore").read_text().splitlines()
		self.assertIn(".env", ignore)

	def test_a_committed_fake_key_is_blocked(self):
		"""SOS-P0-09 test criterion: a fake key staged in a scratch repo makes the hook fail."""
		if not shutil.which("pre-commit"):
			self.skipTest("pre-commit is not installed here; the Linters workflow runs this scan")
		config = (ROOT / ".pre-commit-config.yaml").read_text()
		start = config.index("  - repo: https://github.com/gitleaks/gitleaks")
		end = config.index("  - repo: https://github.com/pre-commit/pre-commit-hooks")
		scratch_config = "repos:\n" + config[start:end]
		# Built in pieces so no key-shaped text sits in this file.
		fake_key = "AKIA" + "IOSFODNN7EXAMPLQ"
		with tempfile.TemporaryDirectory() as tmp:
			scratch = Path(tmp)
			(scratch / ".pre-commit-config.yaml").write_text(scratch_config)
			(scratch / "leak.py").write_text(f'aws_key = "{fake_key}"\n')
			(scratch / "clean.py").write_text("answer = 42\n")
			subprocess.run(["git", "init", "-q"], cwd=scratch, check=True)
			subprocess.run(["git", "add", "-A"], cwd=scratch, check=True)
			blocked = subprocess.run(
				["pre-commit", "run", "gitleaks", "--all-files"],
				cwd=scratch,
				capture_output=True,
				text=True,
				timeout=300,
			)
			self.assertEqual(blocked.returncode, 1, blocked.stdout + blocked.stderr)
			self.assertIn("aws-access-token", blocked.stdout)
			self.assertNotIn(fake_key, blocked.stdout + blocked.stderr)
			(scratch / "leak.py").unlink()
			subprocess.run(["git", "add", "-A"], cwd=scratch, check=True)
			clean = subprocess.run(
				["pre-commit", "run", "gitleaks", "--all-files"],
				cwd=scratch,
				capture_output=True,
				text=True,
				timeout=300,
			)
			self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
