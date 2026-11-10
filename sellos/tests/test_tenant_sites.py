"""SOS-SETUP-22: the provisioner password comes from one function, and tenant sites from one script.

* sellos.provisioning.credentials.get_provisioner_password(): the variable first, else the macOS
  Keychain item sellos_provisioner (a fake security command records how it was asked), else a clear
  error whose message and traceback never hold the value.
* scripts/tenant-site.sh with a fake bench Python that records its arguments and environment: it
  refuses every name but [a-z0-9]+ with exit 2, runs Frappe's new-site and drop-site with
  --db-root-username from SELLOS_DB_PROVISIONER_USER, gives the password to the child only through
  its environment, never prints it, and reads the Keychain when the variable is missing.
* The launcher really hands the password to Frappe's command in memory, not on its command line.
* The real build loop at start: with no variable and no Keychain item it exits 3 and says how to
  store the password, without ever asking the Keychain for the value.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
import unittest
from pathlib import Path
from unittest import mock

from sellos.provisioning import credentials, tenant_sites
from sellos.tests import test_loop_environment_failures as loop_env

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPO_ROOT / "scripts" / "tenant-site.sh"
SECRET = "prov-secret-7b1d4c"
KEYCHAIN_SECRET = loop_env.KEYCHAIN_PASSWORD
STORE = 'security add-generic-password -a "$USER" -s sellos_provisioner -w'
# A fake bench Python: records its arguments (NUL separated, as the launcher code has newlines) and its environment, prints the password
# it was given (the wrapper must redact it), and exits with the code in $FAKE_DIR/bench_exit.
FAKE_BENCH_PYTHON = """#!/usr/bin/env bash
n=$(ls "$FAKE_DIR"/bench_call_*.args 2>/dev/null | wc -l | tr -d ' ')
printf '%s\\0' "$@" >"$FAKE_DIR/bench_call_$n.args"
env >"$FAKE_DIR/bench_call_$n.env"
pwd >"$FAKE_DIR/bench_call_$n.cwd"
echo "Frappe says: connecting as $SELLOS_DB_PROVISIONER_USER with $SELLOS_DB_PROVISIONER_PASSWORD"
exit "$(cat "$FAKE_DIR/bench_exit" 2>/dev/null || echo 0)"
"""
IS_MAC = sys.platform == "darwin"


class Fakes(unittest.TestCase):
	def setUp(self):
		self.root = Path(tempfile.mkdtemp(prefix="sellos-tenant-"))
		self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
		self.fake = self.root / "fake"
		self.bin = self.fake / "bin"
		self.bin.mkdir(parents=True)
		self.bench = self.root / "bench"
		(self.bench / "sites").mkdir(parents=True)
		self.write(self.bin / "security", loop_env.FAKE_SECURITY, 0o755)
		self.write(self.bench / "env/bin/python", FAKE_BENCH_PYTHON, 0o755)

	def write(self, path, text, mode=None):
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(text, encoding="utf-8")
		if mode:
			path.chmod(mode)

	def keychain(self, value=KEYCHAIN_SECRET):
		self.write(self.fake / "keychain", value)

	def security_calls(self):
		path = self.fake / "security_calls"
		return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

	def env(self, **extra):
		env = {
			k: v
			for k, v in os.environ.items()
			if k not in (credentials.PASSWORD_ENV, credentials.USER_ENV, "SELLOS_BENCH_DIR")
		}
		env.update(
			{
				"PATH": f"{self.bin}:{os.environ.get('PATH', '/usr/bin:/bin')}",
				"FAKE_DIR": str(self.fake),
				"SELLOS_BENCH_DIR": str(self.bench),
				"SELLOS_TENANT_PYTHON": sys.executable,
				"PYTHONPATH": str(REPO_ROOT),
			}
		)
		env.update(extra)
		return env

	def bench_calls(self):
		calls = []
		for args in sorted(self.fake.glob("bench_call_*.args")):
			stem = args.with_suffix("")
			env = dict(
				line.split("=", 1)
				for line in Path(f"{stem}.env").read_text(encoding="utf-8").splitlines()
				if "=" in line
			)
			calls.append(
				{
					"args": args.read_text(encoding="utf-8").split("\0")[:-1],
					"env": env,
					"cwd": Path(f"{stem}.cwd").read_text(encoding="utf-8").strip(),
				}
			)
		return calls


class GetProvisionerPassword(Fakes):
	"""In process, with the platform and PATH patched, so it runs the same on macOS and on CI."""

	def call(self, env, platform="darwin"):
		with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(sys, "platform", platform):
			return credentials.get_provisioner_password()

	def base(self, **extra):
		return {"PATH": f"{self.bin}:/usr/bin:/bin", "FAKE_DIR": str(self.fake), **extra}

	def test_the_variable_wins_and_the_keychain_is_not_asked(self):
		self.keychain()
		self.assertEqual(self.call(self.base(SELLOS_DB_PROVISIONER_PASSWORD=SECRET)), SECRET)
		self.assertEqual(self.security_calls(), [])

	def test_the_keychain_is_read_when_the_variable_is_missing(self):
		self.keychain()
		self.assertEqual(self.call(self.base()), KEYCHAIN_SECRET)
		self.assertEqual(self.security_calls(), ["find-generic-password -s sellos_provisioner -w"])

	def test_a_missing_item_raises_a_clear_error_without_any_value(self):
		with self.assertRaises(credentials.ProvisionerPasswordMissing) as ctx:
			self.call(self.base())
		message = str(ctx.exception)
		self.assertIn("Store it once with: " + STORE, message)
		self.assertIn("exited 44", message)
		self.assertNotIn(KEYCHAIN_SECRET, message)

	def test_the_error_and_its_traceback_never_hold_the_value(self):
		# A security command that prints the value and still fails.
		self.write(
			self.bin / "security", f"#!/usr/bin/env bash\necho {SECRET}\necho {SECRET} >&2\nexit 1\n", 0o755
		)
		try:
			self.call(self.base())
		except credentials.ProvisionerPasswordMissing as e:
			text = "".join(traceback.format_exception(e))
			self.assertNotIn(SECRET, text)
			self.assertNotIn(SECRET, repr(e))
		else:
			self.fail("no error was raised")

	def test_a_security_command_that_cannot_run_gives_no_detail(self):
		self.write(self.bin / "security", "not a script", 0o644)
		self.bin.joinpath("security").chmod(0o755)
		with self.assertRaises(credentials.ProvisionerPasswordMissing) as ctx:
			self.call(self.base())
		self.assertIn("could not be read", str(ctx.exception))

	def test_off_macos_the_variable_is_the_only_source(self):
		self.keychain()
		with self.assertRaises(credentials.ProvisionerPasswordMissing) as ctx:
			self.call(self.base(), platform="linux")
		self.assertIn("only read on macOS", str(ctx.exception))
		self.assertEqual(self.security_calls(), [])

	def test_child_env_puts_the_value_only_in_the_environment(self):
		with mock.patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True):
			env = credentials.child_env(SECRET)
		self.assertEqual(env[credentials.PASSWORD_ENV], SECRET)
		self.assertEqual(env[credentials.USER_ENV], "sellos_provisioner")


class TenantSiteScript(Fakes):
	def run_wrapper(self, *args, **env):
		result = subprocess.run(
			["bash", str(WRAPPER), *args], capture_output=True, text=True, env=self.env(**env), timeout=60
		)
		self.out = result.stdout + result.stderr
		return result.returncode

	def assert_never_printed(self, *values):
		for value in values:
			self.assertNotIn(value, self.out)

	def test_other_names_are_refused_with_exit_2_before_anything_runs(self):
		for bad in ("", "A", "a_b", "a-b", "../x", "a.localhost", "x y", "abc\n", "sellos_tenant_a", "é"):
			with self.subTest(bad=bad):
				self.assertEqual(self.run_wrapper("create", bad, SELLOS_DB_PROVISIONER_PASSWORD=SECRET), 2)
				self.assertEqual(self.run_wrapper("drop", bad, SELLOS_DB_PROVISIONER_PASSWORD=SECRET), 2)
		self.assertEqual(self.bench_calls(), [])
		self.assertEqual(self.security_calls(), [])

	def test_wrong_commands_and_argument_counts_exit_2(self):
		for args in ((), ("make", "a"), ("create",), ("create", "a", "b"), ("list", "a"), ("probe", "x")):
			with self.subTest(args=args):
				self.assertEqual(self.run_wrapper(*args), 2)
		self.assertEqual(self.bench_calls(), [])

	def test_the_module_refuses_bad_names_too(self):
		for bad in ("abc\n", "A", "a_b", "x" * 51):
			with self.subTest(bad=bad), self.assertRaises(tenant_sites.TenantNameError):
				tenant_sites.names(bad)
		self.assertEqual(tenant_sites.names("x" * 50)[1], "sellos_tenant_" + "x" * 50)

	def test_create_runs_new_site_with_the_password_only_in_the_environment(self):
		self.assertEqual(
			self.run_wrapper("create", "abc1", SELLOS_DB_PROVISIONER_PASSWORD=SECRET), 0, self.out
		)
		[call] = self.bench_calls()
		self.assertEqual(call["args"][0], "-c")
		self.assertEqual(
			call["args"][2:],
			[
				"new-site",
				"sellos_tenant_abc1.localhost",
				"--db-name",
				"sellos_tenant_abc1",
				"--db-root-username",
				"sellos_provisioner",
			],
		)
		self.assertNotIn(SECRET, "\n".join(call["args"]))
		self.assertEqual(call["env"]["SELLOS_DB_PROVISIONER_PASSWORD"], SECRET)
		self.assertTrue(call["env"].get("SELLOS_TENANT_ADMIN_PASSWORD"))
		self.assertEqual(Path(call["cwd"]).resolve(), (self.bench / "sites").resolve())
		self.assertIn("Created sellos_tenant_abc1.localhost", self.out)
		self.assertIn("[provisioner password]", self.out)
		self.assert_never_printed(SECRET, call["env"]["SELLOS_TENANT_ADMIN_PASSWORD"])
		self.assertEqual(self.security_calls(), [])

	def test_drop_runs_drop_site_with_the_user_from_the_environment(self):
		code = self.run_wrapper(
			"drop", "abc1", SELLOS_DB_PROVISIONER_PASSWORD=SECRET, SELLOS_DB_PROVISIONER_USER="prov2"
		)
		self.assertEqual(code, 0, self.out)
		[call] = self.bench_calls()
		self.assertEqual(
			call["args"][2:],
			["drop-site", "sellos_tenant_abc1.localhost", "--db-root-username", "prov2", "--no-backup"],
		)
		self.assertEqual(call["env"]["SELLOS_DB_PROVISIONER_PASSWORD"], SECRET)
		self.assert_never_printed(SECRET)

	@unittest.skipUnless(IS_MAC, "the Keychain is read only on macOS")
	def test_the_keychain_is_read_when_the_variable_is_missing(self):
		self.keychain()
		self.assertEqual(self.run_wrapper("create", "abc1"), 0, self.out)
		[call] = self.bench_calls()
		self.assertEqual(call["env"]["SELLOS_DB_PROVISIONER_PASSWORD"], KEYCHAIN_SECRET)
		self.assertIn("find-generic-password -s sellos_provisioner -w", self.security_calls())
		self.assert_never_printed(KEYCHAIN_SECRET)

	def test_no_password_anywhere_exits_3_and_runs_nothing(self):
		self.assertEqual(self.run_wrapper("create", "abc1"), 3, self.out)
		self.assertEqual(self.bench_calls(), [])
		if IS_MAC:
			self.assertIn("Store it once with: " + STORE, self.out)
		else:
			self.assertIn("SELLOS_DB_PROVISIONER_PASSWORD is not set", self.out)

	def test_a_failing_command_names_the_site_and_exit_code_never_the_password(self):
		self.write(self.fake / "bench_exit", "1")
		self.assertEqual(self.run_wrapper("create", "abc1", SELLOS_DB_PROVISIONER_PASSWORD=SECRET), 1)
		self.assertIn("new-site sellos_tenant_abc1.localhost failed with exit code 1", self.out)
		self.assertNotIn("Traceback", self.out)
		self.assert_never_printed(SECRET)

	def test_probe_creates_then_drops_and_drops_even_when_create_fails(self):
		self.assertEqual(self.run_wrapper("probe", SELLOS_DB_PROVISIONER_PASSWORD=SECRET), 0, self.out)
		self.assertEqual([c["args"][2] for c in self.bench_calls()], ["new-site", "drop-site"])
		self.assertEqual({c["args"][3] for c in self.bench_calls()}, {"sellos_tenant_probe.localhost"})
		for path in self.fake.glob("bench_call_*"):
			path.unlink()
		self.write(self.fake / "bench_exit", "1")
		self.assertEqual(self.run_wrapper("probe", SELLOS_DB_PROVISIONER_PASSWORD=SECRET), 1)
		self.assertEqual([c["args"][2] for c in self.bench_calls()], ["new-site", "drop-site"])

	def test_list_shows_only_tenant_sites_and_needs_no_password(self):
		for name in (
			"sellos_tenant_a1.localhost",
			"sellos_tenant_b.localhost",
			"sellos_test.localhost",
			"test_site",
		):
			(self.bench / "sites" / name).mkdir()
		self.assertEqual(self.run_wrapper("list"), 0, self.out)
		self.assertEqual(self.out.split(), ["sellos_tenant_a1.localhost", "sellos_tenant_b.localhost"])
		self.assertEqual(self.security_calls(), [])


class Launcher(Fakes):
	"""The launcher with a stand in for frappe.utils.bench_helper that records what it was given."""

	def test_the_password_reaches_frappe_in_memory_and_not_on_the_command_line(self):
		pkg = self.root / "stub" / "frappe" / "utils"
		self.write(self.root / "stub/frappe/__init__.py", "")
		self.write(pkg / "__init__.py", "")
		self.write(
			pkg / "bench_helper.py",
			"import json, os, sys\n"
			f"json.dump({{'argv': sys.argv, 'env': os.environ.get('SELLOS_DB_PROVISIONER_PASSWORD')}}, open({str(self.root / 'seen.json')!r}, 'w'))\n",
		)
		visible = [sys.executable, "-c", tenant_sites.LAUNCHER, "new-site", "sellos_tenant_x.localhost"]
		subprocess.run(
			visible,
			env={
				**os.environ,
				"PYTHONPATH": str(self.root / "stub"),
				"SELLOS_DB_PROVISIONER_PASSWORD": SECRET,
				"SELLOS_TENANT_ADMIN_PASSWORD": "adm-1",
			},
			check=True,
		)
		seen = json.loads((self.root / "seen.json").read_text(encoding="utf-8"))
		# runpy sets argv[0] to the module's file, exactly as python -m frappe.utils.bench_helper does.
		self.assertTrue(seen["argv"][0].endswith("bench_helper.py"), seen["argv"][0])
		self.assertEqual(
			seen["argv"][1:],
			[
				"frappe",
				"new-site",
				"sellos_tenant_x.localhost",
				"--db-root-password",
				SECRET,
				"--admin-password",
				"adm-1",
			],
		)
		self.assertIsNone(seen["env"], "the password stayed in the environment Frappe's children inherit")
		self.assertNotIn(SECRET, " ".join(visible))


class LoopStartCheck(loop_env.LoopSandbox):
	"""The real build loop: the provisioner check at its start."""

	def test_no_variable_and_no_keychain_item_exits_3_with_the_store_command(self):
		self.serve(302)
		(self.fake / "keychain").unlink()
		code = self.run_loop([0])
		self.assertEqual(code, 3, self.out)
		self.assertIn("Store it once with: " + STORE, self.out)
		self.assertEqual(self.calls("claude_calls"), 0)
		self.assertEqual(self.status(), "Not Started")
		self.assertTrue(self.read("security_calls"))
		self.assertNotIn("-w", self.read("security_calls").split())

	def test_an_item_in_the_keychain_is_enough_and_the_agent_never_gets_it(self):
		self.serve(302)
		code = self.run_loop([1], max_runs=1)
		self.assertEqual(code, 0, self.out)
		self.assertEqual(self.calls("claude_calls"), 1, self.out)
		calls = self.read("security_calls").splitlines()
		self.assertEqual(calls[0], "find-generic-password -s sellos_provisioner")
		self.assertNotIn(KEYCHAIN_SECRET, self.out)
		self.assertNotIn(KEYCHAIN_SECRET, self.git("log", "--all", "--format=%B"))

	def test_the_variable_alone_is_enough_and_the_keychain_is_not_read(self):
		self.serve(302)
		(self.fake / "keychain").unlink()
		self.run_loop([1], max_runs=1, extra_env={"SELLOS_DB_PROVISIONER_PASSWORD": SECRET})
		self.assertEqual(self.calls("claude_calls"), 1, self.out)
		self.assertEqual(self.read("security_calls"), "")


class CommitMessage(loop_env.LoopSandbox):
	"""SOS-SETUP-22: the loop's commit subject is "<TASK ID>: <task title>" and the summary is the body."""

	def test_subject_is_the_title_and_the_summary_is_the_body_of_at_most_20_lines(self):
		self.serve(302)
		long_summary = " ".join(f"word{i}" for i in range(600))
		self.write(
			self.bin / "claude",
			f'#!/usr/bin/env bash\necho call >>"$FAKE_DIR/claude_calls"\necho "IMPLEMENTATION_READY: {long_summary}"\n',
			0o755,
		)
		# One green CI run for the pushed commit, so the loop goes on and stops with nothing left.
		self.write(
			self.bin / "gh", '#!/usr/bin/env bash\n[ "$1 $2" = "run list" ] && echo 1\nexit 0\n', 0o755
		)
		self.run_loop([0])
		subject = self.git("log", "-1", "--format=%s", "1.0")
		body = self.git("log", "-1", "--format=%b", "1.0").splitlines()
		self.assertEqual(subject, f"{loop_env.TASK}: a task", self.out)
		self.assertLessEqual(len(body), 20)
		self.assertTrue(body[0].startswith("word0 word1"), body[:2])
		self.assertIn(f"{loop_env.TASK} complete: a task", self.read("notifications"))
