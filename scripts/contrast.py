#!/usr/bin/env python3
"""Contrast ratios (WCAG 2.x) of every SellOS colour pairing. Run: python3 -I scripts/contrast.py
Prints a markdown table; docs/UI_STYLE.md records its output (SOS-UI-2B)."""


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


T900, T700, T500 = rgb("#002D2D"), rgb("#003C3C"), rgb("#004848")
G200, G500, CREAM, WHITE = rgb("#FFDC9C"), rgb("#E4B33C"), rgb("#FFF2DC"), (255, 255, 255)

STATUS = {  # tone: (ink, background, line)
	"success": ("#0B5D3B", "#DDEFDF", "#8FC4A0"),
	"warning": ("#7A4A00", "#FFEBC0", "#E4B33C"),
	"danger": ("#A4281B", "#FBE1DC", "#E0958B"),
	"info": ("#1B5A78", "#DCEAF2", "#8DB6CC"),
}
GHOST = over(T700, WHITE, 0.25)  # secondary button fill on a white card
HOVER_ROW = over(T500, T700, 0.5)  # sidebar hover

PAIRS = [
	("text/onDark on surface/dark (sidebar, top bar)", G200, T700, 4.5),
	("text/accent on surface/dark", G500, T700, 4.5),
	("text/accent on surface/accent (current sidebar item)", G500, T500, 4.5),
	("text/onDark on surface/accent", G200, T500, 4.5),
	("text/onDark on sidebar hover (surface/accent at 50%)", G200, HOVER_ROW, 4.5),
	("text/onLight on surface/cream (page)", T700, CREAM, 4.5),
	("text/onLight on white (cards, inputs)", T700, WHITE, 4.5),
	("text/onLight on surface/gold", T700, G200, 4.5),
	("text/button on button/bg (primary button)", G500, T700, 4.5),
	("text/onLight on button/ghostBg over white (secondary button)", T700, GHOST, 4.5),
	("text/onLight on button/ghostBg over cream", T700, over(T700, CREAM, 0.25), 4.5),
	("link teal/700 on cream", T700, CREAM, 4.5),
	("link teal/700 on white", T700, WHITE, 4.5),
	("input border teal/900 at 55% on white (field)", over(T900, WHITE, 0.55), WHITE, 3.0),
	("card border teal/900 at 20% on cream (decorative)", over(T900, CREAM, 0.20), CREAM, 1.0),
	("NEVER: text/accent gold/500 on surface/gold gold/200", G500, G200, 4.5),
]
for tone, (ink, bg, line) in STATUS.items():
	PAIRS.append((f"{tone} ink on {tone} background (badge)", rgb(ink), rgb(bg), 4.5))
	PAIRS.append((f"{tone} ink on white", rgb(ink), WHITE, 4.5))
	PAIRS.append((f"{tone} ink on cream", rgb(ink), CREAM, 4.5))
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
