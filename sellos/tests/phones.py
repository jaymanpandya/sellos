"""Fake phone numbers for tests. Never write a phone number by hand in a test or a spec.

Every number is checked with the phonenumbers library when it is installed, so a test never fails
on setup because a made up number is invalid. The same seed always gives the same number, and
different seeds give different numbers.
"""

try:
	import phonenumbers
except ImportError:  # the shape checks below still hold without it
	phonenumbers = None

# Seeds are spread over each country's mobile range with a large odd step.
_STEP = 2_654_435_761


def _valid(number):
	if phonenumbers is None:
		return True
	try:
		return phonenumbers.is_valid_number(phonenumbers.parse(number, None))
	except phonenumbers.NumberParseException:
		return False


def _first_valid(build, seed):
	for attempt in range(1000):
		number = build(seed + attempt * 7919)
		if _valid(number):
			return number
	raise ValueError(f"No valid number found for seed {seed}")


def in_mobile(seed=1):
	"""An Indian mobile number: +91 and ten digits that start with 6, 7, 8 or 9."""
	return _first_valid(lambda s: f"+91{6_000_000_000 + (s * _STEP) % 4_000_000_000}", seed)


def au_mobile(seed=1):
	"""An Australian mobile number: +614 and eight digits."""
	return _first_valid(lambda s: f"+614{(s * _STEP) % 100_000_000:08d}", seed)


def ae_mobile(seed=1):
	"""A UAE mobile number: +9715 and eight digits."""
	return _first_valid(lambda s: f"+9715{[0, 2, 4, 5, 6, 8][s % 6]}{(s * _STEP) % 10_000_000:07d}", seed)


def near_in_mobile(seed=1):
	"""An Indian mobile that differs from in_mobile(seed) only in its last digit."""
	base = in_mobile(seed)
	for last in "0123456789":
		other = base[:-1] + last
		if other != base and _valid(other):
			return other
	raise ValueError("No near number found")


def forms(number):
	"""Every way the same number can appear in a response: with the plus, digits only, the national
	ten digits, and spaced. A leak check looks for all of them."""
	digits = number.lstrip("+")
	national = digits[-10:] if number.startswith("+91") else digits[-9:]
	return [number, digits, national, f"{number[:3]} {digits[2:7]} {digits[7:]}"]
