"""The WebSocket end of the voice agent service (SOS-P5-07).

Plivo connects to a wss:// address, and each connection is one call on one company's site. The site is the
one the service was started for, never anything in the message. serve_connection takes any object that
iterates over incoming messages and has a send method, so it runs against a fake socket in tests. `run`
needs the `websockets` package and a port chosen by the person who starts it; the first real call is
SOS-P5-07L. Run it from the bench's sites folder.
"""

import frappe

from sellos.voice.agent import service


def serve_connection(socket, clock=None, adapters=None):
	"""Run one call over `socket`, then queue the Call Log write for a worker, which commits it. Returns
	the session's Result, or None when the stream never started a call."""
	handle = service.run_stream(iter(socket), socket.send, clock=clock, adapters=adapters)
	if handle is None:
		return None
	frappe.enqueue(
		"sellos.voice.agent.service.save_values",
		queue="short",
		log=handle.log,
		values=service.result_values(handle),
	)
	return handle.session.result()


def run(site: str, host: str, port: int):
	"""Serve calls for `site` until stopped."""
	try:
		from websockets.sync.server import serve
	except ImportError:
		raise RuntimeError(
			"The websockets package is not installed, so the voice agent cannot listen."
		) from None

	def handler(socket):
		frappe.init(site=site)
		frappe.connect()
		try:
			serve_connection(socket)
		finally:
			frappe.destroy()

	with serve(handler, host, port, max_size=65536) as server:
		server.serve_forever()
