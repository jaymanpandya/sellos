"""SOS-SETUP-33: every cheap guard in one script, run first by the gate and by the agent.

The real scripts/check-guards.sh runs here in a throwaway repository with the real guard scripts and
sellos/testing/guards.py, a stub pre-commit and a stub Semgrep, so no network and no database is
needed. The guard functions themselves are tested on small trees.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from sellos.testing import guards

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
GUARD_NAMES = (
	"phones",
	"commands",
	"secrets",
	"gate-files",
	"assertion-ratchet",
	"task-evidence",
	"stale-skips",
	"lint",
	"semgrep",
	"serve",
)


def git(cwd, *args):
	return subprocess.run(
		["git", "-c", "user.name=Guard Test", "-c", "user.email=guard@test.invalid", *args],
		cwd=cwd,
		capture_output=True,
		text=True,
		check=True,
	).stdout.strip()


class TestGuardFunctions(unittest.TestCase):
	def setUp(self):
		self.root = Path(tempfile.mkdtemp(prefix="sellos-guards-"))
		self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
		(self.root / "sellos" / "voice").mkdir(parents=True)
		(self.root / "cypress" / "integration").mkdir(parents=True)

	def test_a_literal_number_in_a_test_is_found_with_its_line(self):
		literal = "98765" + "43210"  # built here only so this file passes the guard it tests
		(self.root / "sellos/voice/test_x.py").write_text(f'A = 1\nB = "{literal}"\n', encoding="utf-8")
		found = guards.raw_phone_numbers(self.root)
		self.assertEqual(len(found), 1)
		self.assertTrue(found[0].startswith("sellos/voice/test_x.py:2:"), found)

	def test_a_clean_tree_has_no_number(self):
		(self.root / "sellos/voice/test_x.py").write_text("A = in_mobile(7)\n", encoding="utf-8")
		self.assertEqual(guards.raw_phone_numbers(self.root), [])

	def test_a_command_outside_provisioning_is_found(self):
		(self.root / "sellos/voice/keys.py").write_text("import subprocess\n", encoding="utf-8")
		(self.root / "sellos/provisioning").mkdir()
		(self.root / "sellos/provisioning/credentials.py").write_text("import subprocess\n", encoding="utf-8")
		found = guards.modules_running_commands(self.root / "sellos")
		self.assertEqual(found, ["sellos/voice/keys.py:1 runs commands (subprocess)"])

	def test_each_message_names_its_fix(self):
		self.assertIn("sellos.tests.phones", guards.message("phones", ["x"]))
		self.assertIn("in_mobile(seed)", guards.message("phones", ["x"]))
		self.assertIn("sellos/provisioning", guards.message("commands", ["x"]))

	def test_an_unpinned_serve_command_is_found_and_a_pinned_one_is_not(self):
		"""SOS-SETUP-34: CI run 92 failed on a serve command written with variables."""
		subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
		# Built here only so this file passes the guard it tests.
		unpinned = "bench --site $SITE serve " + "--port $PORT"
		(self.root / "scripts").mkdir()
		(self.root / "scripts/a.sh").write_text(
			f"echo start\n{unpinned}\nbench --site sellos_test.localhost serve --port 8004\n"
			"# never run serve --port 8004 without --site\n",
			encoding="utf-8",
		)
		self.assertEqual(guards.unpinned_serve_commands(self.root), [f"scripts/a.sh:2: {unpinned}"])
		self.assertIn("bench --site sellos_test.localhost serve --port 8004", guards.message("serve", ["x"]))

	def test_the_phone_allowed_list_is_empty(self):
		self.assertEqual(guards.ALLOWED_PHONE_FILES, frozenset())


class CheckGuardsSandbox(unittest.TestCase):
	"""The real scripts/check-guards.sh in a throwaway repository."""

	def setUp(self):
		self.root = Path(tempfile.mkdtemp(prefix="sellos-check-guards-"))
		self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
		self.repo = self.root / "repo"
		(self.repo / "scripts" / "lib").mkdir(parents=True)
		shutil.copy2(SCRIPTS / "check-guards.sh", self.repo / "scripts" / "check-guards.sh")
		for script in SCRIPTS.glob("check_*.py"):
			shutil.copy2(script, self.repo / "scripts" / script.name)
		shutil.copy2(SCRIPTS / "lib" / "tasks.py", self.repo / "scripts" / "lib" / "tasks.py")
		(self.repo / "sellos" / "testing").mkdir(parents=True)
		(self.repo / "sellos" / "__init__.py").write_text("", encoding="utf-8")
		(self.repo / "sellos" / "testing" / "__init__.py").write_text("", encoding="utf-8")
		shutil.copy2(REPO_ROOT / "sellos/testing/guards.py", self.repo / "sellos/testing/guards.py")
		(self.repo / "cypress" / "integration").mkdir(parents=True)
		(self.repo / "TASKS.md").write_text(
			"### SOS-X-1: a task\n- **Status:** In Progress\n", encoding="utf-8"
		)
		(self.repo / ".semgrepignore").write_text("tests/\n", encoding="utf-8")
		self.bin = self.root / "bin"
		self.bin.mkdir()
		self.stub(self.bin / "pre-commit", "exit 0")
		self.semgrep = self.root / "semgrep"
		self.stub(self.semgrep, "exit 0")
		self.rules = self.root / "rules"
		self.rules.mkdir()
		git(self.repo, "init", "-q")
		git(self.repo, "add", "-A")
		git(self.repo, "commit", "-q", "-m", "base")

	def stub(self, path, body):
		path.write_text(f"#!/usr/bin/env bash\n{body}\n", encoding="utf-8")
		path.chmod(0o755)

	def run_guards(self, *args, **env):
		base_env = {
			"PATH": f"{self.bin}:/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
			"HOME": str(self.root),
			"SELLOS_SEMGREP": str(self.semgrep),
			"SELLOS_SEMGREP_RULES": str(self.rules),
		}
		result = subprocess.run(
			["bash", str(self.repo / "scripts/check-guards.sh"), *args],
			cwd=self.repo,
			capture_output=True,
			text=True,
			env={**base_env, **env},
			timeout=120,
		)
		return result.returncode, result.stdout + result.stderr

	def test_a_clean_tree_passes_and_names_every_guard(self):
		code, out = self.run_guards()
		self.assertEqual(code, 0, out)
		self.assertIn("=== GUARDS PASSED", out)
		for name in GUARD_NAMES:
			self.assertIn(f"Guard {name}", out)

	def test_a_literal_number_fails_with_the_fix_first(self):
		literal = "98765" + "43210"
		(self.repo / "sellos/testing/test_probe.py").write_text(f'N = "{literal}"\n', encoding="utf-8")
		code, out = self.run_guards()
		self.assertEqual(code, 1, out)
		block = out.split("GUARD FAILED: phones", 1)[1].split("END GUARD", 1)[0]
		self.assertTrue(block.lstrip().startswith("Fix: Use sellos.tests.phones"), block)
		self.assertIn("sellos/testing/test_probe.py:1:", block)
		self.assertIn("GUARDS FAILED", out)

	def test_every_guard_runs_even_after_one_fails(self):
		(self.repo / "sellos/keys.py").write_text("import subprocess\n", encoding="utf-8")
		self.stub(self.semgrep, 'echo "1 Code Finding"; echo "sellos/keys.py rule"; exit 1')
		code, out = self.run_guards()
		self.assertEqual(code, 1, out)
		self.assertIn("GUARD FAILED: commands", out)
		self.assertIn("GUARD FAILED: semgrep", out)
		self.assertIn("Guard lint: clean.", out)

	def test_an_unpinned_serve_command_fails_with_the_fix(self):
		unpinned = "bench serve " + "--port 8004"
		(self.repo / "scripts/start.sh").write_text(f"{unpinned}\n", encoding="utf-8")
		code, out = self.run_guards()
		self.assertEqual(code, 1, out)
		block = out.split("GUARD FAILED: serve", 1)[1].split("END GUARD", 1)[0]
		self.assertIn("bench --site sellos_test.localhost serve --port 8004", block)
		self.assertIn("scripts/start.sh:1:", block)

	def test_a_lint_failure_on_both_passes_fails(self):
		(self.repo / "sellos/new.py").write_text("x = 1\n", encoding="utf-8")
		self.stub(self.bin / "pre-commit", 'echo "ruff....Failed"; exit 1')
		code, out = self.run_guards()
		self.assertEqual(code, 1, out)
		self.assertIn("GUARD FAILED: lint", out)

	def test_a_deleted_assertion_fails_the_ratchet(self):
		test = self.repo / "sellos/testing/test_ratchet.py"
		test.write_text("def test_a():\n\tassert 1\n\tassert 2\n", encoding="utf-8")
		git(self.repo, "add", "-A")
		git(self.repo, "commit", "-q", "-m", "a test")
		test.write_text("def test_a():\n\tassert 1\n", encoding="utf-8")
		code, out = self.run_guards()
		self.assertEqual(code, 1, out)
		self.assertIn("GUARD FAILED: assertion-ratchet", out)

	def test_a_gate_file_edit_fails_when_a_task_is_set(self):
		base = git(self.repo, "rev-parse", "HEAD")
		block = self.root / "block.md"
		block.write_text("### SOS-X-1: a task\n- **Status:** In Progress\n", encoding="utf-8")
		(self.repo / "sellos/testing/guards.py").write_text("ALLOWED_PHONE_FILES = set()\n", encoding="utf-8")
		code, out = self.run_guards(
			SELLOS_TASK_ID="SOS-X-1", SELLOS_BASE_SHA=base, SELLOS_TASK_BLOCK_FILE=str(block)
		)
		self.assertEqual(code, 1, out)
		self.assertIn("GUARD FAILED: gate-files", out)
		self.assertIn("GUARD FAILED: task-evidence", out)

	def test_missing_semgrep_is_an_environment_problem(self):
		code, out = self.run_guards(SELLOS_SEMGREP=str(self.root / "no-semgrep"))
		self.assertEqual(code, 3, out)
		self.assertIn("This is the environment, not the code.", out)


class TestWhereTheGuardsRun(unittest.TestCase):
	def test_the_gate_runs_the_guards_first(self):
		gate = (SCRIPTS / "run-tests.sh").read_text(encoding="utf-8")
		guards_at = gate.index('"$REPO_DIR/scripts/check-guards.sh" --all')
		self.assertLess(guards_at, gate.index('echo "--- Preflight ---"'))
		self.assertLess(guards_at, gate.index("--- Restoring the clean test site baseline ---"))
		# One copy of the lint and Semgrep commands: the guards script's.
		self.assertNotIn("pre-commit run --all-files ||", gate)

	def test_the_agent_is_told_to_run_them_and_gets_the_guide(self):
		loop = (SCRIPTS / "build-loop.sh").read_text(encoding="utf-8")
		self.assertIn('GUARDS_DOC="$(cat "$PROJECT_DIR/docs/GUARDS.md"', loop)
		self.assertIn("run scripts/check-guards.sh from the app folder", loop)
		prompt = loop.split('PROMPT="You are implementing', 1)[1].split('\nTask:\n$TASK_BLOCK"', 1)[0]
		self.assertIn("$GUARDS_CHECK", prompt)
		# The agent's run sees the task, so the task guards run for it too.
		self.assertLess(loop.index('export SELLOS_TASK_ID="$TASK_ID"'), loop.index('PROMPT="You are'))

	def test_every_guard_is_documented(self):
		doc = (REPO_ROOT / "docs" / "GUARDS.md").read_text(encoding="utf-8")
		for number, name in enumerate(GUARD_NAMES, start=1):
			self.assertIn(f"## {number}. {name}:", doc)
			self.assertIn(f"| {number} | {name} |", doc)
		for part in ("**Why.**", "**How to comply.**", "Do not work around a guard"):
			self.assertIn(part, doc)
