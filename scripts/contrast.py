#!/usr/bin/env python3
"""Contrast ratios (WCAG 2.x) of every SellOS colour pairing. Run: python3 -I scripts/contrast.py
Prints a markdown table; docs/UI_STANDARD.md records its output (SOS-UI-2B)."""


def rgb(h):
	h = h.lstrip("#")
	return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def lum(c):
	def f(v):
		v /= 255
		return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

	r, g, b = [f(v) for v in c]
	return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
	la, lb = lum(a), lum(b)
	return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def over(fg, bg, a):
	return tuple(round(f * a + b * (1 - a)) for f, b in zip(fg, bg, strict=True))


def hx(c):
	return "#%02X%02X%02X" % c


INK, BODY, MUTED = rgb("#1D222B"), rgb("#3F4A5C"), rgb("#525F78")
FIELD, LINE, PAGE, FAINT = rgb("#778399"), rgb("#DDE2EC"), rgb("#F4F5F7"), rgb("#F8F9FB")
BRAND, BRAND_MID, BRAND_SOFT, WHITE = rgb("#0F4C35"), rgb("#2A7A5A"), rgb("#E3F0EA"), (255, 255, 255)

STATUS = {  # tone: (ink, background, line)
	"success": ("#08724E", "#ECFAF5", "#9FE5CD"),
	"warning": ("#8A4B00", "#FEF8ED", "#F5D48A"),
	"danger": ("#BE3910", "#FEF0EC", "#F8B5A1"),
	"info": ("#1A6175", "#EEF8FA", "#AADAE7"),
	"neutral": ("#3F4A5C", "#F0F3F9", "#D5DBE6"),
}

PAIRS = [
	("text on page (ink on neutral page)", INK, PAGE, 4.5),
	("text on white (ink on cards, inputs)", INK, WHITE, 4.5),
	("body text on white (labels)", BODY, WHITE, 4.5),
	("muted text on page (small print, table headings)", MUTED, PAGE, 4.5),
	("muted text on white", MUTED, WHITE, 4.5),
	("menu text on white shell (body)", BODY, WHITE, 4.5),
	("current menu pill (white on brand)", WHITE, BRAND, 4.5),
	("primary button (white on brand)", WHITE, BRAND, 4.5),
	("primary button hover (white on brand mid)", WHITE, BRAND_MID, 4.5),
	("link (brand on white)", BRAND, WHITE, 4.5),
	("link (brand on page)", BRAND, PAGE, 4.5),
	("brand on selected tint", BRAND, BRAND_SOFT, 4.5),
	("input border on white (field)", FIELD, WHITE, 3.0),
	("card border on page (decorative)", LINE, PAGE, 1.0),
]
for tone, (ink, bg, line) in STATUS.items():
	PAIRS.append((f"{tone} ink on {tone} background (badge)", rgb(ink), rgb(bg), 4.5))
	PAIRS.append((f"{tone} ink on white", rgb(ink), WHITE, 4.5))
	PAIRS.append((f"{tone} ink on page", rgb(ink), PAGE, 4.5))
	PAIRS.append((f"{tone} line on {tone} background (border, decorative)", rgb(line), rgb(bg), 1.0))


def main():
	print("| Pairing | Foreground | Background | Ratio | Needs | Result |")
	print("| --- | --- | --- | --- | --- | --- |")
	bad = 0
	for name, fg, bg, need in PAIRS:
		r = ratio(fg, bg)
		ok = r >= need
		if not name.startswith("NEVER") and not ok:
			bad += 1
		print(f"| {name} | {hx(fg)} | {hx(bg)} | {r:.1f} | {need} | {'pass' if ok else 'FAIL'} |")
	return 1 if bad else 0


if __name__ == "__main__":
	raise SystemExit(main())
