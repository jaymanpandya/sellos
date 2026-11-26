"""A small PDF writer for the branded documents (the Private Sale Dossier and the mandate document, SOS-LOOP).

It needs no outside program (the page layout engine wkhtmltopdf is not on every machine) and writes the same
document everywhere: A4 pages, Helvetica text in the Windows Latin 1 set, filled bands, rules, JPEG images, and a
header and footer with "Page N of M" added to every page once the layout is known. Characters outside Latin 1 are
written as "?". Images are re-encoded as JPEG by Pillow, so only what Pillow can open is embedded.
"""

import re
from io import BytesIO

from sellos.inventory.plain_pdf import _clean, _width, _wrap

PAGE_W, PAGE_H = 595, 842
MARGIN = 48
TOP = PAGE_H - 90  # below the running header
BOTTOM = 70  # above the running footer
INK = (0.13, 0.13, 0.13)
MUTED = (0.38, 0.38, 0.38)
IMAGE_SIDE = 1100  # longest side, in pixels, of an embedded picture


def rgb(colour, default=INK):
	if not re.fullmatch(r"#[0-9a-fA-F]{6}", colour or ""):
		return default
	return tuple(int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5))


def prepare_image(content: bytes):
	"""JPEG bytes and the pixel size of an image Pillow can open, or None. Transparency is placed on white."""
	from PIL import Image

	try:
		with Image.open(BytesIO(content)) as image:
			image.load()
			if image.mode in ("RGBA", "LA", "P"):
				image = image.convert("RGBA")
				base = Image.new("RGB", image.size, (255, 255, 255))
				base.paste(image, mask=image.getchannel("A"))
				image = base
			else:
				image = image.convert("RGB")
			image.thumbnail((IMAGE_SIDE, IMAGE_SIDE))
			out = BytesIO()
			image.save(out, "JPEG", quality=82)
			return out.getvalue(), image.size
	except Exception:  # an unreadable picture is left out, never a failure of the document
		return None


class Page:
	def __init__(self, cover=False):
		self.ops: list[bytes] = []
		self.images: list[int] = []  # indexes into Document.images, named /Im<n>
		self.cover = cover

	def text(self, x, y, text, size=10, bold=False, colour=INK, right=False, centre=False):
		width = _width(str(text), size) * (1.08 if bold else 1)
		x = x - width if right else x - width / 2 if centre else x
		r, g, b = colour
		self.ops.append(
			b"BT %.3f %.3f %.3f rg /F%d %.1f Tf %.2f %.2f Td (%s) Tj ET"
			% (r, g, b, 2 if bold else 1, size, x, y, _clean(text))
		)

	def rect(self, x, y, w, h, colour):
		r, g, b = colour
		self.ops.append(b"%.3f %.3f %.3f rg %.2f %.2f %.2f %.2f re f" % (r, g, b, x, y, w, h))

	def rule(self, y, colour, width=1.0, x1=MARGIN, x2=PAGE_W - MARGIN):
		r, g, b = colour
		self.ops.append(
			b"%.3f %.3f %.3f RG %.2f w %.2f %.2f m %.2f %.2f l S" % (r, g, b, width, x1, y, x2, y)
		)

	def image(self, index, x, y, w, h):
		self.images.append(index)
		self.ops.append(b"q %.2f 0 0 %.2f %.2f %.2f cm /Im%d Do Q" % (w, h, x, y, index))


class Document:
	"""Pages in the order they are made. `header` and `footer` are drawn on every page that is not a cover."""

	def __init__(self, brand, title):
		self.brand = brand
		self.title = title
		self.pages: list[Page] = []
		self.images: list[tuple[bytes, tuple[int, int]]] = []
		self.y = TOP
		self.primary = rgb(brand["primary"])
		self.accent = rgb(brand["accent"])

	# --- pages --------------------------------------------------------------------------------------

	@property
	def page(self) -> Page:
		return self.pages[-1]

	def new_page(self, cover=False) -> Page:
		self.pages.append(Page(cover))
		self.y = PAGE_H - MARGIN if cover else TOP
		return self.page

	def need(self, space):
		if not self.pages or self.y - space < BOTTOM:
			self.new_page()

	def space(self, points):
		self.y -= points

	# --- flowing content ----------------------------------------------------------------------------

	def heading(self, text, size=15):
		self.need(size + 30)
		self.space(10)
		self.y -= size
		self.page.text(MARGIN, self.y, text, size, True, self.primary)
		self.y -= 5
		self.page.rule(self.y, self.accent, 1.2)
		self.y -= 10

	def subheading(self, text, size=11.5):
		self.need(size + 16)
		self.space(4)
		self.y -= size
		self.page.text(MARGIN, self.y, text, size, True, self.primary)
		self.y -= 6

	def para(self, text, size=10, colour=INK, indent=0, gap=4, bold=False):
		for part in _wrap(text, size, PAGE_W - 2 * MARGIN - indent) or [""]:
			self.need(size + gap)
			self.y -= size
			self.page.text(MARGIN + indent, self.y, part, size, bold, colour)
			self.y -= gap

	def pair(self, label, value, label_width=130):
		"""A label in muted text and its value, the value wrapped under its own column."""
		lines = _wrap(value, 10, PAGE_W - 2 * MARGIN - label_width) or ["-"]
		self.need(14 * len(lines))
		self.y -= 10
		self.page.text(MARGIN, self.y, label, 9.5, False, MUTED)
		self.page.text(MARGIN + label_width, self.y, lines[0], 10)
		for extra in lines[1:]:
			self.y -= 13
			self.page.text(MARGIN + label_width, self.y, extra, 10)
		self.y -= 5

	def picture(self, content, max_w=240, max_h=170):
		"""Place a picture at the left of the current line and return its width, or 0 when it can not be read."""
		prepared = prepare_image(content)
		if not prepared:
			return 0
		jpeg, (w, h) = prepared
		scale = min(max_w / w, max_h / h, 1.0)
		dw, dh = w * scale, h * scale
		self.need(dh + 8)
		index = len(self.images)
		self.images.append((jpeg, (w, h)))
		self.page.image(index, MARGIN, self.y - dh, dw, dh)
		self.y -= dh + 8
		return dw

	def pictures(self, contents, size=(150, 112)):
		"""A row of pictures, as many as fit across the page, then the next row."""
		per_row = max(1, int((PAGE_W - 2 * MARGIN + 10) // (size[0] + 10)))
		prepared = [p for p in (prepare_image(c) for c in contents) if p]
		for start in range(0, len(prepared), per_row):
			row = prepared[start : start + per_row]
			self.need(size[1] + 10)
			x = MARGIN
			for jpeg, (w, h) in row:
				scale = min(size[0] / w, size[1] / h, 1.0)
				dw, dh = w * scale, h * scale
				index = len(self.images)
				self.images.append((jpeg, (w, h)))
				self.page.image(index, x, self.y - dh, dw, dh)
				x += size[0] + 10
			self.y -= size[1] + 10
		return len(prepared)

	# --- the finished file --------------------------------------------------------------------------

	def _decorate(self):
		b = self.brand
		total = len(self.pages)
		footer = b["footer"] or b["name"]
		for number, page in enumerate(self.pages, 1):
			if page.cover:
				continue
			page.rect(0, PAGE_H - 52, PAGE_W, 52, self.primary)
			white = (1, 1, 1)
			page.text(MARGIN, PAGE_H - 32, b["name"] or self.title, 11, True, white)
			page.text(PAGE_W - MARGIN, PAGE_H - 32, self.title, 9.5, False, white, right=True)
			page.rule(46, self.accent, 0.8)
			if footer:
				page.text(MARGIN, 30, footer[:110], 8.5, False, MUTED)
			page.text(PAGE_W - MARGIN, 30, f"Page {number} of {total}", 8.5, False, MUTED, right=True)
		for number, page in enumerate(self.pages, 1):
			if page.cover:
				page.text(PAGE_W / 2, 30, f"Page {number} of {total}", 8.5, False, MUTED, centre=True)

	def to_bytes(self) -> bytes:
		self._decorate()
		objects: list[bytes] = [b"", b""]
		objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
		objects.append(
			b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
		)
		image_objects = {}
		for index, (jpeg, (w, h)) in enumerate(self.images):
			image_objects[index] = len(objects) + 1
			objects.append(
				b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB "
				b"/BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n%s\nendstream"
				% (w, h, len(jpeg), jpeg)
			)
		kids = []
		for page in self.pages:
			stream = b"\n".join(page.ops)
			content_no, page_no = len(objects) + 2, len(objects) + 1
			kids.append(b"%d 0 R" % page_no)
			xobjects = b" ".join(b"/Im%d %d 0 R" % (i, image_objects[i]) for i in sorted(set(page.images)))
			objects.append(
				b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Contents %d 0 R "
				b"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> /XObject << %s >> >> >>"
				% (PAGE_W, PAGE_H, content_no, xobjects)
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
