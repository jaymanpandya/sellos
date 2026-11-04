"""SOS-SETUP-18: the provisioner account reaches the agent, and its values reach no log.

scripts/lib/db_secrets.sh strips every credential variable from the agent's environment except
SELLOS_DB_PROVISIONER_USER and SELLOS_DB_PROVISIONER_PASSWORD, and redacts their values from what
the loop and the gate write. scripts/check_no_secret_leak.py fails a gate run when the password is
written in a file. These run the real scripts. The whole loop and gate are tested with them in
test_loop_environment_failures.py.
"""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "scripts" / "lib" / "db_secrets.sh"
LEAK = REPO_ROOT / "scripts" / "check_no_secret_leak.py"
USER = "prov-user-3b7e"
PASSWORD = "prov-pass-c19a52"


def bash(script, env, stdin=None):
	return subprocess.run(
		["bash", "-c", f'source "{LIB}"\n{script}'],
		capture_output=True,
		text=True,
		env=env,
		input=stdin,
		timeout=60,
	)


def base_env(**extra):
	keep = ("PATH", "HOME", "TMPDIR", "LANG")
	return {**{k: os.environ[k] for k in keep if k in os.environ}, **extra}


class TestAgentEnvironment(unittest.TestCase):
	def test_only_the_provisioner_credentials_reach_the_agent(self):
		env = base_env(
			SELLOS_DB_PROVISIONER_USER=USER,
			SELLOS_DB_PROVISIONER_PASSWORD=PASSWORD,
			MYSQL_PWD="x1",
			MARIADB_ROOT_PASSWORD="x2",
			SOME_DB_ROOT_PASSWORD="x3",
			SELLOS_DB_OTHER="x4",
			SELLOS_TELEGRAM_BOT_TOKEN="x5",
			SELLOS_TELEGRAM_CHAT_ID="x6",
			GITHUB_TOKEN="x7",
			AWS_SECRET_ACCESS_KEY="x8",
			PLAIN_SETTING="kept",
		)
		result = bash("sellos_agent_env env | cut -d= -f1 | sort", env)
		self.assertEqual(result.returncode, 0, result.stderr)
		names = set(result.stdout.split())
		self.assertLessEqual({"SELLOS_DB_PROVISIONER_USER", "SELLOS_DB_PROVISIONER_PASSWORD", "PATH"}, names)
		self.assertIn("PLAIN_SETTING", names)
		for gone in (
			"MYSQL_PWD",
			"MARIADB_ROOT_PASSWORD",
			"SOME_DB_ROOT_PASSWORD",
			"SELLOS_DB_OTHER",
			"SELLOS_TELEGRAM_BOT_TOKEN",
			"SELLOS_TELEGRAM_CHAT_ID",
			"GITHUB_TOKEN",
			"AWS_SECRET_ACCESS_KEY",
		):
			self.assertNotIn(gone, names)

	def test_the_password_is_inherited_not_put_on_the_command_line(self):
		env = base_env(SELLOS_DB_PROVISIONER_PASSWORD=PASSWORD)
		result = bash(
			'sellos_agent_env bash -c \'printf "%s|" "$SELLOS_DB_PROVISIONER_PASSWORD" "$@"\' x a b', env
		)
		self.assertEqual(result.stdout, f"{PASSWORD}|a|b|")
		# sellos_agent_env runs env with -u options and the command: the value is never an argument.
		trace = bash("set -x; sellos_agent_env true", env)
		self.assertNotIn(PASSWORD, trace.stderr)

	def test_the_user_defaults_to_sellos_provisioner(self):
		result = bash('printf "%s" "$SELLOS_DB_PROVISIONER_USER"', base_env())
		self.assertEqual(result.stdout, "sellos_provisioner")
		result = bash("sellos_agent_env env | grep '^SELLOS_DB_PROVISIONER_USER='", base_env())
		self.assertEqual(result.stdout.strip(), "SELLOS_DB_PROVISIONER_USER=sellos_provisioner")

	def test_without_the_password_the_agent_gets_none(self):
		result = bash("sellos_agent_env env | cut -d= -f1", base_env())
		self.assertNotIn("SELLOS_DB_PROVISIONER_PASSWORD", result.stdout.split())


class TestRedaction(unittest.TestCase):
	def test_values_are_replaced_on_every_line(self):
		env = base_env(SELLOS_DB_PROVISIONER_USER=USER, SELLOS_DB_PROVISIONER_PASSWORD=PASSWORD)
		text = f"one {PASSWORD}\n{USER}:{PASSWORD}@127.0.0.1\nno newline {PASSWORD}"
		result = bash("sellos_redact", env, stdin=text)
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertNotIn(PASSWORD, result.stdout)
		self.assertNotIn(USER, result.stdout)
		self.assertEqual(
			result.stdout,
			"one [provisioner password]\n[provisioner user]:[provisioner password]@127.0.0.1\n"
			"no newline [provisioner password]",
		)

	def test_redact_text_and_bytes_that_are_not_utf8(self):
		env = base_env(SELLOS_DB_PROVISIONER_PASSWORD=PASSWORD)
		result = bash(f'sellos_redact_text "reply: {PASSWORD}"', env)
		self.assertEqual(result.stdout, "reply: [provisioner password]\n")
		raw = subprocess.run(
			[
				"bash",
				"-c",
				f'source "{LIB}"; printf "\\xff\\xfe %s\\n" "$SELLOS_DB_PROVISIONER_PASSWORD" | sellos_redact',
			],
			capture_output=True,
			env=env,
			timeout=60,
		)
		self.assertEqual(raw.stdout, b"\xff\xfe [provisioner password]\n")

	def test_nothing_set_passes_text_through(self):
		result = bash("sellos_redact", base_env(SELLOS_DB_PROVISIONER_USER=""), stdin="plain\n")
		self.assertEqual(result.stdout, "plain\n")


class TestLeakCheck(unittest.TestCase):
	def setUp(self):
		self.dir = Path(tempfile.mkdtemp(prefix="sellos-leak-"))
		self.addCleanup(subprocess.run, ["rm", "-rf", str(self.dir)])

	def leak(self, *args, password=PASSWORD):
		env = base_env(SELLOS_DB_PROVISIONER_PASSWORD=password)
		result = subprocess.run(
			[sys.executable, str(LEAK), *args], capture_output=True, text=True, env=env, timeout=60
		)
		return result.returncode, result.stdout + result.stderr

	def test_a_written_password_fails_with_the_place_and_never_the_value(self):
		log = self.dir / "logs" / "bench.log"
		log.parent.mkdir()
		log.write_text(f"line one\nbench new-site x --db-root-password {PASSWORD}\n", encoding="utf-8")
		code, out = self.leak(str(self.dir / "logs"))
		self.assertEqual(code, 1, out)
		self.assertIn(f"{log}:2", out)
		self.assertNotIn(PASSWORD, out)

	def test_a_value_across_a_chunk_boundary_is_found(self):
		big = self.dir / "big.log"
		big.write_bytes(b"a" * ((1 << 20) - 5) + PASSWORD.encode() + b"\n")
		code, out = self.leak(str(big))
		self.assertEqual(code, 1, out)
		self.assertIn(f"{big}:1", out)

	def test_clean_files_pass_and_git_and_node_modules_are_skipped(self):
		(self.dir / "ok.txt").write_text("nothing here\n", encoding="utf-8")
		for skipped in (".git", "node_modules"):
			(self.dir / skipped).mkdir()
			(self.dir / skipped / "x").write_text(PASSWORD, encoding="utf-8")
		code, out = self.leak(str(self.dir), str(self.dir / "missing"))
		self.assertEqual(code, 0, out)

	def test_since_skips_a_file_nobody_wrote_to(self):
		old = self.dir / "old.log"
		old.write_text(PASSWORD, encoding="utf-8")
		past = time.time() - 3600
		os.utime(old, (past, past))
		self.assertEqual(self.leak("--since", str(time.time() - 60), str(self.dir))[0], 0)
		self.assertEqual(self.leak(str(self.dir))[0], 1)

	def test_without_a_password_there_is_nothing_to_find(self):
		(self.dir / "x.log").write_text("anything", encoding="utf-8")
		code, out = self.leak(str(self.dir), password="")
		self.assertEqual(code, 0, out)
		self.assertIn("not set", out)


if __name__ == "__main__":
	unittest.main()
