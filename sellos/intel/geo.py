"""Boundary checks for a micro market (SOS-P3-04). A boundary is optional GeoJSON: a Polygon, a MultiPolygon,
or a Feature or FeatureCollection holding them. It is only read and stored, never looked up elsewhere."""

import json

import frappe
from frappe import _

AREAS = ("Polygon", "MultiPolygon")
WRAPPERS = ("Feature", "FeatureCollection")


def _position(point) -> bool:
	return (
		isinstance(point, list)
		and len(point) >= 2
		and all(isinstance(n, (int, float)) and not isinstance(n, bool) for n in point[:2])
		and -180 <= point[0] <= 180
		and -90 <= point[1] <= 90
	)


def _ring(ring) -> bool:
	return (
		isinstance(ring, list) and len(ring) >= 4 and all(_position(p) for p in ring) and ring[0] == ring[-1]
	)


def _polygon(rings) -> bool:
	return isinstance(rings, list) and bool(rings) and all(_ring(r) for r in rings)


def _geometry_ok(node) -> bool:
	if not isinstance(node, dict):
		return False
	kind = node.get("type")
	if kind == "Polygon":
		return _polygon(node.get("coordinates"))
	if kind == "MultiPolygon":
		parts = node.get("coordinates")
		return isinstance(parts, list) and bool(parts) and all(_polygon(p) for p in parts)
	if kind == "Feature":
		return _geometry_ok(node.get("geometry"))
	if kind == "FeatureCollection":
		features = node.get("features")
		return isinstance(features, list) and bool(features) and all(_geometry_ok(f) for f in features)
	return False


def check_boundary(value):
	"""The boundary as compact JSON text, or "" when none was given. Throws when it is not usable GeoJSON."""
	if value in (None, "", {}):
		return ""
	try:
		node = json.loads(value) if isinstance(value, str) else value
	except ValueError:
		node = None
	if not _geometry_ok(node):
		frappe.throw(
			_(
				"The boundary must be GeoJSON: a Polygon or MultiPolygon, or a Feature or FeatureCollection of them."
			)
		)
	return json.dumps(node, separators=(",", ":"))
