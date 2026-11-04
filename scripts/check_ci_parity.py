#!/usr/bin/env python3
"""Fails when the local bench is not the bench CI builds (SOS-SETUP-17).

Usage: check_ci_parity.py <BENCH_DIR> [WORKFLOW_FILE]
WORKFLOW_FILE defaults to .github/workflows/ci.yml, relative to the working directory.

On 4 November 2026 every UI spec failed in CI and passed on Jayman's machine. CI's `bench init` named
no Frappe branch and got Frappe's develop branch, which has no cypress/support folder, so
cypress/support/e2e.js could not import Frappe's commands. The local bench is on version-16. This
check compares what CI installs with what the local bench runs:

* every `bench init` in the workflow names a Frappe branch with --frappe-branch, and all name the same,
* the local apps/frappe is checked out on that branch,
* the bench's Python has the major and minor version of every python-version in the workflow,
* the Node on PATH has the major version of every node-version in the workflow.

The gate runs it in its preflight. A mismatch is an environment problem (the gate exits 3).
"""

import re
import subprocess
import sys
from pathlib import Path

# Any line that runs bench init, as a step of its own or in a block, but not a comment about it.
BENCH_INIT = re.compile(r"^[^#\n]*\bbench init\b.*$", re.M)
FRAPPE_BRANCH = re.compile(r"--frappe-branch[ =](\S+)")
PYTHON_VERSION = re.compile(r"^\s*python-version:\s*['\"]?([0-9.]+)['\"]?\s*$", re.M)
NODE_VERSION = re.compile(r"^\s*node-version:\s*['\"]?([0-9.]+)['\"]?\s*$", re.M)


def run(cmd, cwd=None):
	result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
	return result.returncode, (result.stdout + result.stderr).strip()


def problems(bench, workflow):
	text = workflow.read_text(encoding="utf-8")
	out = []

	inits = BENCH_INIT.findall(text)
	if not inits:
		out.append(f"{workflow} has no `bench init`, so the Frappe branch CI uses is unknown.")
	branches = set()
	for line in inits:
		m = FRAPPE_BRANCH.search(line)
		if m:
			branches.add(m.group(1))
		else:
			out.append(
				f"{workflow}: `{line.strip()}` names no --frappe-branch, so CI gets Frappe's default branch."
			)
	if len(branches) > 1:
		out.append(f"{workflow}: the jobs install different Frappe branches: {', '.join(sorted(branches))}.")
	if len(branches) == 1:
		want = branches.pop()
		code, have = run(["git", "symbolic-ref", "--short", "HEAD"], cwd=bench / "apps" / "frappe")
		if code != 0:
			out.append(f"Cannot read the Frappe branch in {bench / 'apps' / 'frappe'}: {have}")
		elif have != want:
			out.append(f"CI installs Frappe {want}, and {bench / 'apps' / 'frappe'} is on {have}.")

	pythons = set(PYTHON_VERSION.findall(text))
	if pythons:
		code, have = run([str(bench / "env" / "bin" / "python"), "--version"])
		local = re.search(r"(\d+\.\d+)", have)
		for want in sorted(pythons):
			if code != 0 or not local or local.group(1) != ".".join(want.split(".")[:2]):
				out.append(f"CI uses Python {want}, and the bench's Python is {have or 'missing'}.")

	nodes = set(NODE_VERSION.findall(text))
	if nodes:
		try:
			code, have = run(["node", "--version"])
		except FileNotFoundError:
			code, have = 1, ""
		local = re.search(r"v?(\d+)", have)
		for want in sorted(nodes):
			if code != 0 or not local or local.group(1) != want.split(".")[0]:
				out.append(f"CI uses Node {want}, and the Node on PATH is {have or 'missing'}.")
	return out


def main(argv):
	if not argv:
		print("Usage: check_ci_parity.py <BENCH_DIR> [WORKFLOW_FILE]")
		return 2
	bench = Path(argv[0])
	workflow = Path(argv[1]) if len(argv) > 1 else Path(".github/workflows/ci.yml")
	found = problems(bench, workflow)
	if found:
		print("The local bench is not the bench CI builds:")
		for line in found:
			print(f"  {line}")
		return 1
	print("CI parity: the Frappe branch, Python and Node match CI.")
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
