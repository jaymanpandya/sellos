#!/usr/bin/env python3
"""Fails when a gate run touched a site that is not SellOS's to touch (SOS-SETUP-17).

Usage:
  check_site_set.py snapshot <BENCH_DIR> <SNAPSHOT_FILE>
  check_site_set.py compare  <BENCH_DIR> <SNAPSHOT_FILE>

The bench at ~/iespl-bench holds BuildOS's and Pamaa's sites beside SellOS's. A gate run may touch
only the gate's own site (sellos_test.localhost) and the test tenant sites, which are always named
sellos_tenant_<id>.localhost (SOS-P0-06L). The gate takes a snapshot in its preflight and compares at
the end. The compare fails when:

* a site folder that is not one of those appeared or disappeared,
* the site_config.json of any other site changed,
* a tenant site that did not exist at the snapshot is still there (a test must drop what it makes).

It sees site folders and their configs. It does not see the databases, so the tenant code itself must
refuse any other name before it runs a command (SOS-P0-06L).
"""

import hashlib
import json
import re
import sys
from pathlib import Path

TENANT_SITE = re.compile(r"^sellos_tenant_[a-z0-9_]+\.localhost$")
GATE_SITES = {"sellos_test", "sellos_test.localhost"}


def is_tenant(name):
	return bool(TENANT_SITE.match(name))


def ours(name):
	return name in GATE_SITES or is_tenant(name)


def sites(bench):
	"""{site name: sha256 of its site_config.json} for every site folder of the bench."""
	root = Path(bench) / "sites"
	found = {}
	for path in sorted(root.iterdir()) if root.is_dir() else []:
		config = path / "site_config.json"
		if path.is_dir() and config.is_file():
			found[path.name] = hashlib.sha256(config.read_bytes()).hexdigest()
	return found


def problems(before, after):
	out = []
	for name in sorted(set(before) | set(after)):
		if ours(name):
			if is_tenant(name) and name in after and name not in before:
				out.append(f"{name} was created by this run and is still there. Drop it in the test.")
			continue
		if name not in after:
			out.append(
				f"{name} was removed. Only sellos_test.localhost and sellos_tenant_<id>.localhost may be touched."
			)
		elif name not in before:
			out.append(f"{name} was created. Test tenant sites are named sellos_tenant_<id>.localhost.")
		elif before[name] != after[name]:
			out.append(f"{name}/site_config.json changed. It is not a SellOS test site.")
	return out


def main(argv):
	if len(argv) != 3 or argv[0] not in ("snapshot", "compare"):
		print(__doc__.split("\n\n")[1])
		return 2
	action, bench, snapshot = argv
	if action == "snapshot":
		Path(snapshot).write_text(json.dumps(sites(bench), indent=1), encoding="utf-8")
		return 0
	before = json.loads(Path(snapshot).read_text(encoding="utf-8"))
	found = problems(before, sites(bench))
	if found:
		print("This run touched sites that are not SellOS test sites, or left tenant sites behind:")
		for line in found:
			print(f"  {line}")
		return 1
	print("Sites: only sellos_test.localhost and test tenant sites were touched, and no tenant was left.")
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
