import datetime
import os
import re
import sys
from zoneinfo import ZoneInfo

if os.environ.get("SELLOS_LIMIT_WAIT_OVERRIDE"):
	print(int(os.environ["SELLOS_LIMIT_WAIT_OVERRIDE"]))
	sys.exit(0)
t = sys.argv[1] if len(sys.argv) > 1 else ""
wait = 1800
m = re.search(r"resets\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*\(([^)]+)\)", t, re.I)
try:
	if m:
		h = int(m.group(1))
		mi = int(m.group(2) or 0)
		ap = (m.group(3) or "").lower()
		if ap == "pm" and h < 12:
			h += 12
		if ap == "am" and h == 12:
			h = 0
		tz = ZoneInfo(m.group(4).strip().replace("Calcutta", "Kolkata"))
		now = datetime.datetime.now(tz)
		target = now.replace(hour=h, minute=mi, second=0, microsecond=0)
		if target <= now:
			target += datetime.timedelta(days=1)
		wait = int((target - now).total_seconds()) + 120
except Exception:
	wait = 1800
print(min(max(wait, 60), 8 * 3600))
