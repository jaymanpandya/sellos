#!/usr/bin/env python3
"""The SellOS demo server (SOS-DEMO-1): Host header routing for the demo sites, on 127.0.0.1:8006.

Run by the bench's own Python from the bench's sites folder (scripts/demo.sh start does it, as the
LaunchAgent com.sellos.demo):

    cd ~/iespl-bench/sites && ../env/bin/python <repo>/scripts/lib/demo_server.py [--port 8006]

* The site comes from the Host header: sellos_tenant_demo<id>.localhost:8006. `bench serve` cannot do
  this on this bench, because it picks default_site when no --site is given and then serves that site
  (BuildOS's) for every host name, the 4 November 2026 mistake (docs/DEV_STRATEGY.md).
* Any other Host, and any X-Frappe-Site-Name header, is answered 404 before Frappe sees it, so the
  server can never serve BuildOS, Pamaa or the gate's site.
* It binds 127.0.0.1 only (Frappe's own serve binds every interface), because the demo has known
  passwords.
* No reloader: it does not restart when the loop edits files.
"""

import sys

import frappe.app
from werkzeug.serving import run_simple
from werkzeug.wrappers import Response

from sellos.testing.demo import PORT, is_demo_site


def only_demo_hosts(app):
	def guarded(environ, start_response):
		environ.pop("HTTP_X_FRAPPE_SITE_NAME", None)
		host = environ.get("HTTP_HOST", "").split(":", 1)[0]
		if not is_demo_site(host):
			return Response("Not a demo site.", status=404)(environ, start_response)
		return app(environ, start_response)

	return guarded


def build():
	frappe.app._site = None  # the Host header picks the site
	frappe.app._sites_path = "."
	return only_demo_hosts(frappe.app.application_with_statics())


def main(argv):
	port = PORT
	if argv[:1] == ["--port"]:
		port = int(argv[1])
	run_simple("127.0.0.1", port, build(), use_reloader=False, use_debugger=False, threaded=True)
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
