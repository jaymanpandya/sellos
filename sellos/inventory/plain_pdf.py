"""SOS-P7-07: a cost sheet as a PDF without any outside program.

The page layout engine (wkhtmltopdf) is not on every machine. This writes the same figures as a plain
one page (or more) PDF with the standard Helvetica font, so the sheet can always be opened.
"""

import re

PAGE_W, PAGE_H, MARGIN = 595, 842, 40
# Helvetica widths (per 1000 em) for the characters a sheet is mostly made of; the rest use 556.
_WIDTHS = {" ": 278, ",": 278, ".": 278, "-": 333, "%": 889, "R": 722, "s": 500, "(": 333, ")": 333}


def _width(text, size) -> float:
	return sum(_WIDTHS.get(c, 556) for c in text) * size / 1000


def _clean(text) -> bytes:
	data = str(text).encode("cp1252", "replace")
	return data.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _rgb(colour) -> tuple[float, float, float]:
	if not re.fullmatch(r"#[0-9a-fA-F]{6}", colour or ""):
		return (0.1, 0.1, 0.1)
	return tuple(int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5))


class _Page:
	def __init__(self):
		self.ops: list[bytes] = []

	def text(self, x, y, text, size=10, bold=False, colour=(0.13, 0.13, 0.13), right=False):
		if right:
			x -= _width(str(text), size)
		r, g, b = colour
		font = b"/F2" if bold else b"/F1"
		self.ops.append(
			b"BT %.3f %.3f %.3f rg %s %d Tf %.2f %.2f Td (%s) Tj ET"
			% (r, g, b, font, size, x, y, _clean(text))
		)

	def rule(self, y, colour, width=2):
		r, g, b = colour
		self.ops.append(
			b"%.3f %.3f %.3f RG %d w %d %.2f m %d %.2f l S" % (r, g, b, width, MARGIN, y, PAGE_W - MARGIN, y)
		)


def build_pdf(view, inr) -> bytes:
	"""The bytes of a PDF for a cost sheet view (see sheet_view); `inr` formats rupees."""
	brand = view["brand"]
	colour = _rgb(brand["colour"])
	left, right = MARGIN, PAGE_W - MARGIN
	pages = [_Page()]
	state = {"y": PAGE_H - MARGIN}

	def page():
		return pages[-1]

	def need(space):
		if state["y"] - space < MARGIN:
			pages.append(_Page())
			state["y"] = PAGE_H - MARGIN

	def line(text, size=10, bold=False, gap=4, col=(0.13, 0.13, 0.13)):
		need(size + gap)
		state["y"] -= size
		page().text(left, state["y"], text, size, bold, col)
		state["y"] -= gap

	def row(label, amount, bold=False):
		need(16)
		state["y"] -= 12
		page().text(left, state["y"], label, 10, bold)
		page().text(right, state["y"], inr(amount), 10, bold, right=True)
		state["y"] -= 4

	line(brand["name"], 18, True, 4, colour)
	contact = " | ".join(p for p in (brand["phone"], brand["email"]) if p)
	if contact:
		line(contact, 9)
	if brand["address"]:
		line(brand["address"], 9)
	page().rule(state["y"] - 2, colour)
	state["y"] -= 14
	line(f"Cost sheet {view['name']}", 14, True, 6)
	floor = view["floor"] if view["floor"] is not None else "-"
	line(f"{view['project_name']} - Unit {view['unit_number']}, {view['configuration']}", 10)
	line(f"{view['carpet_area']} sq ft carpet area, floor {floor}, {view['parking']} parking", 10)
	line(
		f"Price list: {view['price_list_title']} (in force from {view['price_list_from']}). "
		f"Made on {str(view['made_on'])[:10]} by {view['made_by']}.",
		9,
		gap=10,
	)
	line("Price", 12, True, 6, colour)
	row(f"Base price ({view['carpet_area']} sq ft at {inr(view['base_rate'])} per sq ft)", view["base_price"])
	if view["floor_rise_amount"]:
		row(f"Floor rise (floor {view['floor']})", view["floor_rise_amount"])
	for charge in view["charges"]:
		row(charge["charge_name"], charge["amount"])
	row("Agreement value", view["agreement_value"], True)
	row(f"Stamp duty ({view['stamp_duty_percent']}%)", view["stamp_duty"])
	row(f"Registration ({view['registration_percent']}%)", view["registration"])
	row(f"GST ({view['gst_percent']}%)", view["gst"])
	row("Total", view["total"], True)
	state["y"] -= 10
	line(f"Payment plan: {view['plan_name']} ({view['plan_type']})", 12, True, 6, colour)
	columns = (left, left + 250, left + 400, right)
	need(16)
	state["y"] -= 12
	for x, head, align in zip(
		columns, ("Instalment", "Due on", "Percent", "Amount"), (0, 0, 1, 1), strict=True
	):
		page().text(x, state["y"], head, 10, True, right=bool(align))
	state["y"] -= 4
	for i in view["instalments"]:
		need(16)
		state["y"] -= 12
		page().text(columns[0], state["y"], i["label"], 10)
		page().text(columns[1], state["y"], str(i["due_on"]), 10)
		page().text(columns[2] + 50, state["y"], f"{i['percent']}%", 10, right=True)
		page().text(columns[3], state["y"], inr(i["amount"]), 10, right=True)
		state["y"] -= 4
	state["y"] -= 8
	line(
		"Amounts are in rupees, rounded to the rupee. Stamp duty, registration and GST are worked on the "
		"agreement value.",
		8,
	)
	return _assemble([b"\n".join(p.ops) for p in pages])


def _assemble(streams) -> bytes:
	objects: list[bytes] = [b"", b""]  # 1 catalog, 2 page tree, filled below
	objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
	objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
	kids = []
	for stream in streams:
		content_no = len(objects) + 2
		page_no = len(objects) + 1
		kids.append(b"%d 0 R" % page_no)
		objects.append(
			b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Contents %d 0 R "
			b"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> >>" % (PAGE_W, PAGE_H, content_no)
		)
		objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
	objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
	objects[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(kids), len(kids))
	out = bytearray(b"%PDF-1.4\n")
	offsets = []
	for number, body in enumerate(objects, 1):
		offsets.append(len(out))
		out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
	xref = len(out)
	out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
	for offset in offsets:
		out += b"%010d 00000 n \n" % offset
	out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
	return bytes(out)


def _wrap(text, size, limit) -> list[str]:
	"""Break text into lines no wider than `limit` points."""
	lines, line = [], ""
	for word in str(text).split():
		trial = f"{line} {word}".strip()
		if line and _width(trial, size) > limit:
			lines.append(line)
			line = word
		else:
			line = trial
	return [*lines, line] if line else lines


def build_shortlist_pdf(view, inr) -> bytes:
	"""SOS-P7-09: a shortlist as a plain PDF, for a machine without the page layout program. The same lines as
	the layout version (company, client, agent, each home with its price, note and what is no longer
	available) without the pictures; the layout version carries the photos."""
	brand = view["brand"]
	colour = _rgb(brand["colour"])
	left, right = MARGIN, PAGE_W - MARGIN
	pages = [_Page()]
	state = {"y": PAGE_H - MARGIN}

	def line(text, size=10, bold=False, gap=4, col=(0.13, 0.13, 0.13), indent=0):
		for part in _wrap(text, size, right - left - indent) or [""]:
			if state["y"] - size - gap < MARGIN:
				pages.append(_Page())
				state["y"] = PAGE_H - MARGIN
			state["y"] -= size
			pages[-1].text(left + indent, state["y"], part, size, bold, col)
			state["y"] -= gap

	line(brand["name"], 18, True, 4, colour)
	contact = " | ".join(p for p in (brand["phone"], brand["email"]) if p)
	if contact:
		line(contact, 9)
	if brand["address"]:
		line(brand["address"], 9)
	pages[-1].rule(state["y"] - 2, colour)
	state["y"] -= 14
	line(view["title"], 14, True, 6)
	line(f"Chosen for {view['client_name']} on {view['made_on']}", 9)
	agent = view["agent"]
	line("Your contact: " + " | ".join(p for p in (agent["name"], agent["phone"]) if p), 9, gap=8)
	if view["note"]:
		line(view["note"], 10, gap=8)
	for item in view["items"]:
		price = inr(item["price"]) if item["price"] else "Price on request"
		line(f"{item['position']}. {item['title']}", 11, True, 2, colour)
		facts = " | ".join(p for p in (item["configuration"], item["locality"]) if p)
		line(f"{price}" + (f" | {facts}" if facts else ""), 10, indent=14)
		if item["unavailable"]:
			line(str(item["reason"]), 10, True, 2, (0.7, 0, 0.13), indent=14)
		if item["note"]:
			line(item["note"], 9, indent=14)
		state["y"] -= 6
	line("Prices are in rupees and may change. A home marked as no longer available is not on offer.", 8)
	return _assemble([b"\n".join(p.ops) for p in pages])
