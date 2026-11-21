"""Small real files for tests (SOS-P7-01). Frappe reads an uploaded PDF, so a made up byte string is refused."""

import base64
import io


def tiny_pdf() -> bytes:
	"""A valid one page PDF."""
	from pypdf import PdfWriter

	writer = PdfWriter()
	writer.add_blank_page(width=72, height=72)
	out = io.BytesIO()
	writer.write(out)
	return out.getvalue()


def tiny_pdf_base64() -> str:
	return base64.b64encode(tiny_pdf()).decode()
