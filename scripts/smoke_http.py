#!/usr/bin/env python3
"""HTTP smoke checks against a running SellOS test server.

It logs in as the real test users and opens /sellos, so it proves that the users exist, that
login works, and that the built app is served with the right boot data. Uses only the standard
library. Reads SELLOS_SMOKE_BASE and SELLOS_SMOKE_USERS (a JSON list of email and password).
"""

import http.cookiejar
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
	def redirect_request(self, req, fp, code, msg, headers, newurl):
		return None


def fetch(opener, url, data=None):
	"""Return (status, headers, body). Never raises on an HTTP error status."""
	body = urllib.parse.urlencode(data).encode() if data is not None else None
	try:
		with opener.open(urllib.request.Request(url, data=body), timeout=30) as r:
			return r.status, r.headers, r.read().decode("utf-8", "replace")
	except urllib.error.HTTPError as e:
		return e.code, e.headers, e.read().decode("utf-8", "replace")


def new_opener(follow=True, jar=None):
	jar = jar if jar is not None else http.cookiejar.CookieJar()
	handlers = [urllib.request.HTTPCookieProcessor(jar)]
	if not follow:
		handlers.append(NoRedirect())
	return urllib.request.build_opener(*handlers)


def main():
	base = os.environ["SELLOS_SMOKE_BASE"].rstrip("/")
	users = json.loads(os.environ.get("SELLOS_SMOKE_USERS", "[]"))
	results = []

	def check(name, ok, detail=""):
		results.append((name, bool(ok), detail))
		print(("PASS  " if ok else "FAIL  ") + name + (f"  ({detail})" if detail and not ok else ""))

	check("test users were supplied", len(users) > 0, "the fixture returned no users")

	status, headers, _ = fetch(new_opener(follow=False), f"{base}/sellos")
	check(
		"guest is sent to the login page",
		status in (301, 302) and "/login" in (headers.get("Location") or ""),
		f"status {status}, location {headers.get('Location')}",
	)

	for user in users:
		email, password = user["email"], user["password"]

		bad = new_opener()
		status, _, _ = fetch(bad, f"{base}/api/method/login", {"usr": email, "pwd": password + "x"})
		check(f"{email}: wrong password is refused", status in (401, 403), f"status {status}")

		jar = http.cookiejar.CookieJar()
		opener = new_opener(jar=jar)
		status, _, body = fetch(opener, f"{base}/api/method/login", {"usr": email, "pwd": password})
		# Frappe answers "Logged In" to desk users and "No App" to website users. Both are logins.
		try:
			login = json.loads(body)
		except ValueError:
			login = {}
		logged_in = status == 200 and login.get("message") in ("Logged In", "No App")
		check(f"{email}: login works", logged_in, f"status {status}: {body[:120]}")
		if not logged_in:
			continue
		if user.get("roles") and not user.get("desk"):
			check(
				f"{email}: lands on the web app after login",
				login.get("home_page") == "/sellos",
				f"home page is {login.get('home_page')}",
			)

		status, _, html = fetch(opener, f"{base}/sellos")
		check(f"{email}: /sellos opens", status == 200, f"status {status}")
		check(f"{email}: page holds the app root", 'id="app"' in html)
		check(f"{email}: boot data names the user", f'"user": "{email}"' in html)
		missing = [role for role in user.get("roles", []) if f'"{role}"' not in html]
		check(f"{email}: boot data lists the roles", not missing, f"missing {missing}")

		# The desk lives at /desk in Frappe 16. Only users marked desk may open it.
		status, headers, _ = fetch(new_opener(follow=False, jar=jar), f"{base}/desk/user")
		if user.get("desk"):
			check(f"{email}: can open the desk", status == 200, f"status {status}")
		else:
			check(
				f"{email}: is kept out of the desk",
				status != 200,
				f"status {status}: /desk/user opened",
			)

		assets = re.findall(r'(?:src|href)="(/assets/sellos/frontend/[^"]+\.(?:js|css))"', html)
		check(f"{email}: page links built assets", len(assets) > 0, "no built assets in the page")
		for asset in assets:
			status, _, _ = fetch(opener, base + asset)
			check(f"{email}: asset {asset.rsplit('/', 1)[-1]} loads", status == 200, f"status {status}")

	failed = [name for name, ok, _ in results if not ok]
	print(f"\n{len(results) - len(failed)} of {len(results)} checks passed")
	return 1 if failed else 0


if __name__ == "__main__":
	sys.exit(main())
