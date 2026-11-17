"""Text normalisation for scoring (SOS-N21A).

Both sides are normalised before they are compared: case and punctuation go, and spoken Hindi or
English numbers become digits, so "teen crore" and "3 crore", "do crore pachaas lakh" and "2.5 crore",
and "nau aath saat" and "987" match. Amounts with crore, lakh or hazaar become one rupee figure.
"""

import re
from decimal import Decimal

DIGIT_WORDS = {
	"zero": 0, "shunya": 0, "sifar": 0,
	"ek": 1, "one": 1,
	"do": 2, "two": 2,
	"teen": 3, "three": 3,
	"chaar": 4, "char": 4, "four": 4,
	"paanch": 5, "panch": 5, "five": 5,
	"chhe": 6, "chhah": 6, "chah": 6, "che": 6, "chhey": 6, "six": 6,
	"saat": 7, "sat": 7, "seven": 7,
	"aath": 8, "ath": 8, "eight": 8,
	"nau": 9, "nine": 9,
}  # fmt: skip
OTHER_WORDS = {
	"das": 10, "ten": 10, "gyarah": 11, "gyaarah": 11, "eleven": 11, "barah": 12, "twelve": 12,
	"terah": 13, "thirteen": 13, "chaudah": 14, "fourteen": 14, "pandrah": 15, "fifteen": 15,
	"solah": 16, "sixteen": 16, "satrah": 17, "seventeen": 17, "atharah": 18, "eighteen": 18,
	"unnis": 19, "nineteen": 19, "bees": 20, "twenty": 20, "pachees": 25, "tees": 30, "thirty": 30,
	"paintees": 35, "chalis": 40, "forty": 40, "paintalis": 45, "pachaas": 50, "fifty": 50,
	"saath": 60, "sixty": 60, "sattar": 70, "seventy": 70, "assi": 80, "eighty": 80,
	"nabbe": 90, "ninety": 90,
}  # fmt: skip
HUNDRED_WORDS = {"sau", "hundred"}
MULTIPLIERS = {
	"hazaar": 1000, "hazar": 1000, "thousand": 1000,
	"lakh": 100000, "lakhs": 100000, "lac": 100000, "lacs": 100000,
	"crore": 10000000, "crores": 10000000, "cr": 10000000,
}  # fmt: skip

_LITERAL = re.compile(r"\d+(?:\.\d+)?$")


def _tokens(text):
	text = re.sub(r"(?<=\d),(?=\d)", "", text.lower())
	text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)
	text = re.sub(r"[^\w.]+", " ", text)
	return text.split()


def _kind(token):
	if _LITERAL.match(token):
		return "literal"
	if token in DIGIT_WORDS:
		return "digit"
	if token in OTHER_WORDS:
		return "word"
	if token in HUNDRED_WORDS:
		return "hundred"
	if token in MULTIPLIERS:
		return "multiplier"
	return None


def _plain(value):
	text = format(value.normalize(), "f")
	return text


def _value(token):
	if token in DIGIT_WORDS:
		return Decimal(DIGIT_WORDS[token])
	if token in OTHER_WORDS:
		return Decimal(OTHER_WORDS[token])
	return Decimal(token)


def _amount(run):
	"""One figure for a run that holds crore, lakh, hazaar or sau: 'do crore pachaas lakh' is 25000000."""
	total, current = Decimal(0), Decimal(0)
	for token in run:
		kind = _kind(token)
		if kind == "hundred":
			current = (current or Decimal(1)) * 100
		elif kind == "multiplier":
			total += (current or Decimal(1)) * MULTIPLIERS[token]
			current = Decimal(0)
		else:
			current += _value(token)
	return _plain(total + current)


def _plain_run(run):
	"""Numbers with no multiplier: consecutive digit words are read out digit by digit ('nau aath' is 98)."""
	out, digits = [], []
	for token in run:
		if _kind(token) == "digit":
			digits.append(str(DIGIT_WORDS[token]))
			continue
		if digits:
			out.append("".join(digits))
			digits = []
		out.append(_plain(_value(token)))
	if digits:
		out.append("".join(digits))
	return out


def normalise(text):
	"""The normalised tokens of `text`: lower case, no punctuation, spoken numbers as digits."""
	tokens = _tokens(text)
	out, i = [], 0
	while i < len(tokens):
		if _kind(tokens[i]) is None:
			out.append(tokens[i])
			i += 1
			continue
		j = i
		while j < len(tokens) and _kind(tokens[j]) is not None:
			j += 1
		run = tokens[i:j]
		if any(_kind(t) in ("multiplier", "hundred") for t in run):
			out.append(_amount(run))
		else:
			out.extend(_plain_run(run))
		i = j
	return out


def normalise_text(text):
	return " ".join(normalise(text))
