# Scraper runtime (SOS-P6-08)

The portal scraper drives a headless browser. It does not run in the bench's Python, so nothing was added
to the shared bench (SOS-SETUP-20). It has its own environment, outside the repository and the bench.

| Item | Value (installed 27 November 2026) |
|---|---|
| Virtual environment | `~/iespl-baseline/scraper-venv` (Python 3.14.7, from Homebrew) |
| Interpreter | `~/iespl-baseline/scraper-venv/bin/python` |
| Playwright | 1.65.2 (installed with pip into that venv only) |
| Browsers folder | `~/iespl-baseline/scraper-browsers` (set with `PLAYWRIGHT_BROWSERS_PATH`) |
| Chromium | Chrome for Testing 159.0.8154.6 at `scraper-browsers/chromium-1255/` and a headless shell at `scraper-browsers/chromium_headless_shell-1255/` |

## Smoke test (27 November 2026)

Launched headless Chromium from the venv, loaded a local HTML file, read its title (`Smoke ok`) and an
element's text, and closed the browser: passed. It made no network request.

## How P6-08 uses it

* The scraper worker reads the interpreter path and the browsers folder from settings (the site setting
  `scraper_python` and `scraper_browsers_path`, or the environment variables `SELLOS_SCRAPER_PYTHON` and
  `SELLOS_SCRAPER_BROWSERS`), never from a path in code. A new machine sets two values and runs the two commands
  below; nothing is tied to this laptop or to Pandya.
* The worker starts the scraper as a child process of that interpreter with `PLAYWRIGHT_BROWSERS_PATH` set,
  so the bench's Python never imports Playwright.
* A setting that points at a missing interpreter or browser fails the source's health check loudly and
  alerts. It never falls back to the bench's Python.
* Tests drive the adapters against saved pages only (SOS-P6-08). No test and no loop run reaches a live portal.

## Set up on another machine

```
python3.14 -m venv <venv>
<venv>/bin/python -m pip install playwright
PLAYWRIGHT_BROWSERS_PATH=<browsers> <venv>/bin/python -m playwright install chromium
```

Upgrading Playwright means repeating the last two commands and recording the new versions here.
