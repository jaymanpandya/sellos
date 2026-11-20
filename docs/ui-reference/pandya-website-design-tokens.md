# Pandya Realtors website: design tokens

Source: Figma file "Property Possibilities", page "Pandya Realtors - Website", artboard "Pandya Realtors - Home Page" (1728 wide desktop). Tokens were created as Figma variables and text styles in the same file on 18 Nov 2026. Text is solid colour only. Gradients remain on shapes only.

## Colour primitives (collection: Primitives, hidden from pickers)

| Token | Value | CSS variable |
|---|---|---|
| color/teal/900 | #002D2D | var(--color-teal-900) |
| color/teal/700 | #003C3C | var(--color-teal-700) |
| color/teal/500 | #004848 | var(--color-teal-500) |
| color/gold/200 | #FFDC9C | var(--color-gold-200) |
| color/gold/500 | #E4B33C | var(--color-gold-500) |
| color/cream/100 | #FFF2DC | var(--color-cream-100) |
| color/teal/700a25 | #003C3C at 25% | var(--color-teal-700-a25) |

## Colour semantic (collection: Color)

| Token | Points to | Use |
|---|---|---|
| surface/dark | teal/700 | Header, process, butler, footer bands |
| surface/darkest | teal/900 | Deepest surfaces, borders on light |
| surface/accent | teal/500 | Subtle raised areas on dark |
| surface/gold | gold/200 | Service band, cards, quote bar, final call to action |
| surface/cream | cream/100 | Page background |
| text/onDark | gold/200 | All text on teal and on the hero photo |
| text/onLight | teal/700 | All text on cream and on pale gold |
| text/accent | gold/500 | Emphasis on teal, such as list titles |
| text/button | gold/500 | Labels on teal buttons |
| border/default | teal/900 | Borders on light |
| border/onDark | gold/500 | Dividers on teal |
| button/bg | teal/700 | Primary button fill |
| button/ghostBg | teal/700a25 | Secondary button fill |
| button/ghostBorder | teal/900 | Secondary button border |

Contrast checked: text/onDark on surface/dark 9.3, text/accent on surface/dark 6.3, text/onLight on surface/cream 11.1, text/onLight on surface/gold 9.3. Do not put gold/500 text on gold/200 (1.5).

## Typography (website only; SellOS keeps PAMAA's fonts and type scale, see docs/UI_STYLE.md)

| Style | Font | Size / line height | Status |
|---|---|---|---|
| Display/Hero | stangith Regular | 84 / 84 | Variables ready, Figma style pending font |
| Heading/H1 | stangith Regular | 60 / 60 | Variables ready, Figma style pending font |
| Heading/H2 | stangith Regular | 40 / 48 | Variables ready, Figma style pending font |
| Lead | Figtree Light | 30 / 36 | Created and applied |
| Body | Figtree Light | 20 / 24 | Created and applied |
| Label (eyebrow, uppercase) | Figtree Light | 16 / 20 | Created and applied |
| Small | Figtree Light | 14 / auto | Created and applied |
| Button/Default | Figtree SemiBold | 18 / auto | Created and applied |
| Button/Large | Figtree SemiBold | 20 / auto | Created and applied |
| Step Number | Figtree SemiBold | 32 / auto | Created and applied |

## Spacing and shape

Spacing: xs 4, sm 8, md 14, lg 24, xl 48, page margin 69. Radius: sm 8 (buttons), md 16 (cards, images), full 100 (step circles). Grid: 1728 canvas, 69 margin, three columns for cards and four for process steps. Teal bands are 660 tall.
