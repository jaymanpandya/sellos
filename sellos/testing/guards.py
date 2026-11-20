"""The code guards, in one place, with the standard library only (SOS-SETUP-33).

A guard checks the code itself rather than a feature. Two of them used to live only inside backend
tests, so the agent learnt about them after a twelve minute suite run, and on 13 November 2026
SOS-N21A was Blocked by one of them. They live here so that `scripts/check-guards.sh` runs them in
a second, without a database or a bench, and the backend tests run the same functions:

* raw_phone_numbers: sellos/tests/test_no_raw_phone_numbers.py (SOS-P1-06)
* modules_running_commands: sellos/provisioning/test_p1_02_worker.py (SOS-P1-02)
* raw_controls (SOS-UI-2B follow up): a .vue page outside frontend/src/components that writes a raw <button>,
  <input> or <select> instead of the shared components (docs/UI_STYLE.md). docs/ui-backlog.txt lists the
  pages that still do, and only shrinks.
* unpinned_serve_commands: sellos/tests/test_sellos_server_port.py (SOS-SETUP-13). Added by SOS-SETUP-34:
  CI run 92 failed on 9cbace7 because a hand commit wrote the serve command with variables, and only
  the full suite ran this check.

Each returns the list of offending places, empty when the code is clean. `message()` gives the text
the guard prints and the test asserts with: what is wrong, then the fix it names. docs/GUARDS.md
explains each guard.
"""

import ast
import re
import subprocess
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
	"serve": (
		"Write every serve command as the pinned SellOS one, literally: "
		"bench --site sellos_test.localhost serve --port 8004 (no variables for the site or the port). "
		"A line that warns against the unpinned form names it after the word 'without' and '--site'."
	),
	"controls": (
		"Build the page from the shared components in frontend/src/components (AppButton, FormField, "
		"MoneyField, AppCheckbox, StatusBadge, ListCard, FilterBar, PageHeader) and docs/UI_STYLE.md, never a "
		"raw <button>, <input> or <select>. Follow the Leads list and the lead page. A page already on "
		"docs/ui-backlog.txt comes off it when it is converted; nothing is ever added to it."
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


PINNED_SERVE = "--site sellos_test.localhost serve --port 8004"
SERVE_SUFFIXES = frozenset({".md", ".sh", ".js", ".py"})
# The guard and its test name the unpinned form to look for it.
SERVE_SELF_FILES = frozenset({"sellos/tests/test_sellos_server_port.py", "sellos/testing/guards.py"})


def unpinned_serve_commands(root=APP_ROOT):
	"""'path:line: text' for every serve command in the repository that is not the pinned SellOS one."""
	files = subprocess.run(
		["git", "ls-files", "--cached", "--others", "--exclude-standard"],
		cwd=root,
		capture_output=True,
		text=True,
		check=True,
	).stdout.split()
	found = []
	for rel in files:
		path = root / rel
		if rel.startswith(("docs/legacy/", "frontend/node_modules/")) or not path.is_file():
			continue
		if path.suffix not in SERVE_SUFFIXES or rel in SERVE_SELF_FILES:
			continue
		for n, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
			# A line warning against the unpinned form names it next to "without --site".
			warning = "without" in line and "--site" in line.split("without", 1)[1]
			if "serve --port" in line and PINNED_SERVE not in line and not warning:
				found.append(f"{rel}:{n}: {line.strip()}")
	return found


# SOS-UI-2B follow up: the screens use frappe-ui through the shared components (AppButton, FormField,
# MoneyField, StatusBadge, AppCheckbox...). A page outside frontend/src/components may not write a raw
# <button>, <input> or <select>. The pages that still do are listed in docs/ui-backlog.txt, the starting
# backlog: a page not on it that writes one fails, and a page on it that no longer does must come off it.
CONTROL_BACKLOG = "docs/ui-backlog.txt"
SHARED_FOLDER = "frontend/src/components/"
RAW_CONTROL = re.compile(r"<(button|input|select)(?=[\s/>])")
BLANKABLE = re.compile(r"<script\b.*?</script>|<style\b.*?</style>|<!--.*?-->", re.S)


def _controls_in(text):
	"""(line, tag) of the first raw control in a .vue file's template, or None."""
	template = BLANKABLE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
	match = RAW_CONTROL.search(template)
	return (template.count("\n", 0, match.start()) + 1, match.group(0)) if match else None


def backlog_pages(root=APP_ROOT):
	path = root / CONTROL_BACKLOG
	if not path.exists():
		return set()
	lines = (line.split("#", 1)[0].strip() for line in path.read_text(encoding="utf-8").splitlines())
	return {line for line in lines if line}


def raw_controls(root=APP_ROOT):
	"""Lines for every page outside the shared components that writes a raw control and is not on the
	backlog, and for every backlog entry that no longer needs to be there."""
	listed = backlog_pages(root)
	found = []
	offenders = set()
	for path in sorted((root / "frontend" / "src").rglob("*.vue")):
		rel = path.relative_to(root).as_posix()
		if rel.startswith(SHARED_FOLDER):
			continue
		hit = _controls_in(path.read_text(encoding="utf-8"))
		if not hit:
			continue
		offenders.add(rel)
		if rel not in listed:
			found.append(f"{rel}:{hit[0]}: {hit[1]}>")
	for rel in sorted(listed - offenders):
		found.append(
			f"{CONTROL_BACKLOG}: {rel} has no raw control now, or is gone; remove it from the backlog"
		)
	return found


CHECKS = {
	"phones": raw_phone_numbers,
	"commands": modules_running_commands,
	"serve": unpinned_serve_commands,
	"controls": raw_controls,
}


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
