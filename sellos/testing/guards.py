"""The code guards, in one place, with the standard library only (SOS-SETUP-33).

A guard checks the code itself rather than a feature. Two of them used to live only inside backend
tests, so the agent learnt about them after a twelve minute suite run, and on 13 November 2026
SOS-N21A was Blocked by one of them. They live here so that `scripts/check-guards.sh` runs them in
a second, without a database or a bench, and the backend tests run the same functions:

* raw_phone_numbers: sellos/tests/test_no_raw_phone_numbers.py (SOS-P1-06)
* modules_running_commands: sellos/provisioning/test_p1_02_worker.py (SOS-P1-02)

Each returns the list of offending places, empty when the code is clean. `message()` gives the text
the guard prints and the test asserts with: what is wrong, then the fix it names. docs/GUARDS.md
explains each guard.
"""

import ast
import re
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = APP_ROOT / "sellos"

# SOS-P1-06: the allowed list is empty and stays empty.
ALLOWED_PHONE_FILES = frozenset()
# The guard's own test and the generator's test name the patterns they check.
PHONE_SELF_FILES = frozenset({"test_no_raw_phone_numbers.py", "test_phones.py"})

# +91 followed by digits, or a ten digit national number that starts with 6 to 9, in a string.
RAW_PHONE = (
	re.compile(r"\+91[\s-]?\d"),
	re.compile(r"""["'`(\s]([6-9]\d{9})["'`)\s,;]"""),
	re.compile(r"\+614\d"),
	re.compile(r"\+9715\d"),
)

COMMAND_MODULES = frozenset({"subprocess", "pty", "pexpect"})
COMMAND_CALLS = frozenset({"os.system", "os.popen"})
# Only these folders of the sellos package may run commands, plus test files.
COMMAND_FOLDERS = ("provisioning", "tests", "testing")

FIXES = {
	"phones": (
		"Use sellos.tests.phones, never a literal number. Generate the number with in_mobile(seed) "
		"(or au_mobile, ae_mobile, near_in_mobile) and derive every other form from it, such as "
		"its ten national digits or its spoken words. Do not disguise a literal (no joins, ranges, "
		"concatenation or escapes): that is working around the guard."
	),
	"commands": (
		"Only sellos/provisioning runs commands (SOS-P1-02). Call a helper in that package "
		"(credentials.py for the Keychain, tenant_sites.py for sites), adding one there if none "
		"fits, and import it. Do not move the module into a skipped folder to escape the guard."
	),
}


def phone_files(root=APP_ROOT):
	yield from (root / "sellos").rglob("test_*.py")
	yield from (root / "cypress" / "integration").rglob("*.cy.js")


def raw_phone_numbers(root=APP_ROOT):
	"""'path:line: text' for every hand written phone number in a test or a spec."""
	found = []
	for path in sorted(phone_files(root)):
		relative = path.relative_to(root).as_posix()
		if relative in ALLOWED_PHONE_FILES or path.name in PHONE_SELF_FILES:
			continue
		for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
			if any(pattern.search(line) for pattern in RAW_PHONE):
				found.append(f"{relative}:{number}: {line.strip()[:80]}")
	return found


def modules_running_commands(package=PACKAGE):
	"""'path runs commands (name)' for every module outside the allowed folders that runs one."""
	found = []
	for path in sorted(package.rglob("*.py")):
		rel = path.relative_to(package)
		if rel.parts[0] in COMMAND_FOLDERS or path.name.startswith("test_"):
			continue
		tree = ast.parse(path.read_text(encoding="utf-8"))
		for node in ast.walk(tree):
			if isinstance(node, ast.Import):
				names = {a.name.split(".")[0] for a in node.names}
			elif isinstance(node, ast.ImportFrom):
				names = {(node.module or "").split(".")[0]}
			elif isinstance(node, ast.Call) and ast.unparse(node.func) in COMMAND_CALLS:
				names = {ast.unparse(node.func)}
			else:
				continue
			hit = names & (COMMAND_MODULES | COMMAND_CALLS)
			if hit:
				found.append(
					f"sellos/{rel.as_posix()}:{node.lineno} runs commands ({', '.join(sorted(hit))})"
				)
	return found


CHECKS = {"phones": raw_phone_numbers, "commands": modules_running_commands}


def message(name, found):
	"""The guard's failure text: what is wrong, then the fix it names."""
	return f"{FIXES[name]}\n" + "\n".join(found)


def main(argv):
	names = argv or list(CHECKS)
	failed = 0
	for name in names:
		found = CHECKS[name]()
		if found:
			failed = 1
			print(f"GUARD FAILED: {name}")
			print(f"Fix: {message(name, found)}")
			print("END GUARD")
		else:
			print(f"Guard {name}: clean.")
	return failed


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
