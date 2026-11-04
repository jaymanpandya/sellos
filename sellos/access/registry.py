"""Every sellos API method declares its allowed roles (P1.04).

Use `@sellos_api(AGENT, COMPANY_ADMIN)` instead of `@frappe.whitelist()`. The decorator records the
roles, checks them on every call, and whitelists the function. A whitelisted sellos method with no
declaration is refused by `guard_api`, which runs before every request. There is no role that
skips the check. (Frappe's built in Administrator account passes `frappe.only_for`, as it does
everywhere in Frappe.)
"""

import functools
import importlib
import re

import frappe

PREFIX = "sellos."

# dotted method path -> frozenset of role names
_REGISTRY: dict[str, frozenset[str]] = {}

_METHOD_PATH = re.compile(r"^/api/(?:v\d+/)?method/(?P<method>[^?]+)$")


def sellos_api(*roles, methods=None):
	"""Declare a whitelisted method and the roles that may call it. At least one role is required."""
	if not roles or not all(isinstance(role, str) and role for role in roles):
		raise ValueError("sellos_api needs at least one role name")
	allowed = frozenset(roles)

	def decorate(fn):
		path = f"{fn.__module__}.{fn.__name__}"
		_REGISTRY[path] = allowed

		@functools.wraps(fn)
		def checked(*args, **kwargs):
			frappe.only_for(sorted(allowed))
			return fn(*args, **kwargs)

		return frappe.whitelist(methods=methods or ["GET", "POST"])(checked)

	return decorate


def allowed_roles(method_path: str) -> frozenset[str] | None:
	"""The declared roles for a method, or None when it has no declaration."""
	return _REGISTRY.get(method_path)


def declared_methods() -> dict[str, frozenset[str]]:
	return dict(_REGISTRY)


def undeclared_whitelisted_methods() -> list[str]:
	"""Whitelisted functions in the sellos package that have no declaration."""
	found = []
	for fn in frappe.whitelisted:
		path = f"{fn.__module__}.{fn.__name__}"
		if path.startswith(PREFIX) and path not in _REGISTRY:
			found.append(path)
	return sorted(found)


def method_from_path(path: str) -> str | None:
	match = _METHOD_PATH.match(path or "")
	return match.group("method") if match else None


_loaded = False


def load_declared_modules():
	"""Import every module that holds a sellos API method, so `_REGISTRY` is complete (P1.06A).

	`_REGISTRY` is filled by importing a module that uses `@sellos_api`, and a fresh server process
	has imported none of them when its first request arrives. The guard runs before Frappe imports
	the method, so without this every declared method was refused until something else imported its
	module, and the refused call never did. The module list is the permission matrix, which a test
	keeps equal to the declarations. A method that is in no listed module is still not in the
	registry, so it is still refused: this adds no method and lifts no refusal.
	"""
	global _loaded
	if _loaded:
		return
	from sellos.access.matrix import MATRIX

	for module in sorted({path.rsplit(".", 1)[0] for path in MATRIX}):
		importlib.import_module(module)
	_loaded = True


def is_refused(method: str | None) -> bool:
	"""True for a sellos method that has no declared roles."""
	if method and method.startswith(PREFIX):
		load_declared_modules()
	return bool(method) and method.startswith(PREFIX) and method not in _REGISTRY


def guard_api():
	"""before_request hook: a sellos method with no declaration is denied."""
	request = frappe.local.request
	if not request:
		return
	# `cmd` can name a method on the old style endpoint as well as in the path
	method = method_from_path(request.path) or request.values.get("cmd")
	if is_refused(method):
		raise frappe.PermissionError(frappe._("This method has no declared roles."))
