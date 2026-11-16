#!/usr/bin/env python3
"""The Cypress specs a task's changes can break, found before any test runs (SOS-SETUP-37).

On 14 November 2026 SOS-P1-20 turned the lead form's Source field into a required select and updated
the one spec that typed into it. Two older specs made a lead through the same form without choosing a
source, so their save never happened. They failed only in the whole Cypress suite at the end of the
gate, three gate runs in a row, and the task was Blocked (docs/STOPS.md, "task broke older specs").

A spec is affected when it uses something the task changed:

* a test id (data-testid="sellos-<id>") anywhere in a changed frontend file, in the file as it was or
  as it is now, so an id the task removed or renamed counts too. A spec uses an id through
  cy.getByTestId("<id>") or the full sellos-<id>. Every id in the file counts, not only those on
  changed lines: a new required field breaks a spec that never touched that field.
* a function the task changed in a changed Python file, named in the spec by its dotted path: an API
  method a spec intercepts or calls (sellos.crm.api.save_lead) or a fixture it runs through cy.bench
  (sellos.tests.ui_fixtures.seed_agent_leads).

  affected_specs.py <app folder> <base revision> <changed file>...

Prints one line per affected spec, "<spec under cypress/integration><TAB><why>", in path order. The
specs the task changed itself are left out: the gate runs those anyway.
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

TESTID_IN_SOURCE = re.compile(r"""data-testid\s*=\s*["']sellos-([A-Za-z0-9_-]+)["']""")
TESTID_BY_HELPER = re.compile(r"""getByTestId\(\s*["'`]([A-Za-z0-9_-]+)["'`]""")
TESTID_IN_SPEC = re.compile(r"sellos-([A-Za-z0-9_-]*[A-Za-z0-9])")
FRONTEND = re.compile(r"^frontend/src/.*\.(vue|js|ts)$")
SPEC = re.compile(r"^cypress/integration/.*\.cy\.js$")
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.M)


def git(app, *args):
	return subprocess.run(["git", "-C", str(app), *args], capture_output=True, text=True, check=False)


def old_text(app, base, path):
	result = git(app, "show", f"{base}:{path}")
	return result.stdout if result.returncode == 0 else ""


def new_text(app, path):
	try:
		return (Path(app) / path).read_text(encoding="utf-8")
	except (FileNotFoundError, UnicodeDecodeError):
		return ""


def test_ids(app, base, path):
	return set(TESTID_IN_SOURCE.findall(old_text(app, base, path))) | set(
		TESTID_IN_SOURCE.findall(new_text(app, path))
	)


def functions(text):
	"""Top level functions of a Python source: {name: (first line, last line)}, decorators included."""
	try:
		tree = ast.parse(text)
	except SyntaxError:
		return {}
	found = {}
	for node in tree.body:
		if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
			first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
			found[node.name] = (first, node.end_lineno or node.lineno)
	return found


def overlaps(span, ranges):
	return any(start <= span[1] and span[0] <= end for start, end in ranges)


def changed_functions(app, base, path):
	"""The functions in path that the diff from base touches, or that it added or removed."""
	before, after = old_text(app, base, path), new_text(app, path)
	old_funcs, new_funcs = functions(before), functions(after)
	if not before:
		return set(new_funcs)
	diff = git(app, "diff", "-U0", base, "--", path).stdout
	old_ranges, new_ranges = [], []
	for match in HUNK.finditer(diff):
		o_start, o_len, n_start, n_len = match.groups()
		o_start, n_start = int(o_start), int(n_start)
		o_len = 1 if o_len is None else int(o_len)
		n_len = 1 if n_len is None else int(n_len)
		old_ranges.append((o_start, o_start + max(o_len, 1) - 1))
		new_ranges.append((n_start, n_start + max(n_len, 1) - 1))
	changed = {name for name, span in new_funcs.items() if overlaps(span, new_ranges)}
	changed |= {name for name, span in old_funcs.items() if overlaps(span, old_ranges)}
	changed |= set(old_funcs) ^ set(new_funcs)
	return changed


def module_of(path):
	return path[: -len(".py")].replace("/", ".")


def affected(app, base, changed):
	app = Path(app)
	changed = [c for c in changed if c]
	ids = set()
	for path in changed:
		if FRONTEND.match(path):
			ids |= test_ids(app, base, path)
	methods = set()
	for path in changed:
		if path.endswith(".py") and path.startswith("sellos/"):
			methods |= {f"{module_of(path)}.{name}" for name in changed_functions(app, base, path)}
	own = {c for c in changed if SPEC.match(c)}
	results = []
	for spec in sorted((app / "cypress" / "integration").rglob("*.cy.js")):
		rel = spec.relative_to(app).as_posix()
		if rel in own:
			continue
		text = spec.read_text(encoding="utf-8")
		used = (set(TESTID_BY_HELPER.findall(text)) | set(TESTID_IN_SPEC.findall(text))) & ids
		called = {m for m in methods if re.search(re.escape(m) + r"(?![A-Za-z0-9_])", text)}
		if not used and not called:
			continue
		why = []
		if used:
			names = sorted(used)
			why.append(
				"test ids " + ", ".join(names[:5]) + (f" and {len(names) - 5} more" if len(names) > 5 else "")
			)
		if called:
			why.append("calls " + ", ".join(sorted(called)[:3]))
		results.append((rel[len("cypress/integration/") :], "; ".join(why)))
	return results


def main(argv):
	if len(argv) < 2:
		print(__doc__, file=sys.stderr)
		return 2
	app, base, *changed = argv
	for spec, why in affected(app, base, changed):
		print(f"{spec}\t{why}")
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
