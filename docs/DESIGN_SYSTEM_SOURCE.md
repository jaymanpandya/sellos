# One design system for BuildOS, PAMAA and SellOS

Version 1, 24 November 2026. Written so that any of the three products can copy it and look the same.
PAMAA is the reference: its screens are the target, and every value below was read from PAMAA's own
theme files and shared components, then checked against its screenshots.

## 1. Why BuildOS looked worse than PAMAA

PAMAA is built from about a dozen shared pieces, and every screen is made only from them. A screen cannot
draw its own heading, card, button, stat figure, status word or empty state, so every screen looks like
the same family. BuildOS had none of those pieces. Each of its 80 plus pages drew its own, so every page
drifted: different heading weights, grey buttons here and black buttons there, plain text for empty
states, one narrow column with a wide empty column beside it.

The rule that fixes this, and the one SellOS must follow from its first screen:

**A page is assembled from the shared pieces. If a page needs something the pieces do not offer, the
piece is extended first. Pages never style their own headings, cards, buttons, figures or status words.**

## 2. Tokens (the only place a value is written)

| Token | Value |
|---|---|
| Card radius | 14px (cards, panels, dialogs, menus that open from a button, boxed notes) |
| Control radius | 10px (buttons, fields, selects, sidebar items, small rectangular chips) |
| Round | fully round (icon badges, avatars, status pills, count badges) |
| Touch height | 44px minimum for every button, field, select and menu row |
| Card padding | 16px, and 20px from 640px wide |
| Gap between stacked cards | 16px |
| Gap inside a field grid | 20px across, 16px down |
| Page margin | 16px on a phone, 24px from 640px wide, content no wider than 1440px |
| Card shadow | 0 1px 2px rgba(17,24,39,0.04), 0 6px 20px -8px rgba(17,24,39,0.10) |
| Lift shadow (hover, popovers) | 0 2px 4px rgba(17,24,39,0.05), 0 14px 32px -12px rgba(17,24,39,0.18) |
| Button shadow (solid button) | 0 1px 2px rgba(dark brand,0.25), 0 4px 12px -4px rgba(brand,0.4) |
| Motion | 120ms fast, 180ms base, 250ms slow, curve cubic-bezier(0.16, 1, 0.3, 1), all switched off for people who ask their device to reduce motion |
| Font | Inter, then system fonts |
| Type floor | PAMAA: 14px for small print, 16px for everything people read for more than a word. A product may set a higher floor (BuildOS sets 16px for everything, by the owner's choice). Never lower than the product's floor |

Colour comes from three groups, each defined once:

1. Neutrals: ink #1D222B for text, body #3F4A5C for secondary text, muted #525F78 for small print and table
   headings, line #DDE2EC for borders, line soft #EBEEF4 for row dividers, field #8A96AD for input
   borders, page tint from #F4F5F7 to #EEF1F8, faint #F8F9FB for quiet boxes.
2. Brand: one brand colour with a soft tint, a gradient from the brand to a slightly lighter shade for
   solid buttons and the active menu item, and a darker shade for text on tints. Each product keeps its own
   brand colours (BuildOS uses the logo blue and green; PAMAA uses indigo); nothing else in this document
   changes between products.
3. Status colours, each with ink, background and line: success (green), warn (amber), danger (red),
   info (brand blue), neutral (grey). A status is always a word and an icon with a tint, never a colour
   alone.

Every area of the product (for example Sales, Calls, Projects, Money, Safety, Settings) has one accent,
one soft tint, one dark ink and one icon, defined once and used everywhere that area appears: the sidebar
section chip, the page header icon, card top edges, stat figures and empty states.

## 3. The shared pieces

Every product builds these, with the same names, props and look. Below is what each one is.

| Piece | What it is |
|---|---|
| App shell | Sidebar on the left (240px, white with a soft blur), a sticky top bar (61px tall), the page area. On a phone and tablet the sidebar becomes a bottom bar with a More drawer. |
| Sidebar | Logo mark (36px rounded square, brand gradient, white letter) and the product name in letter spaced capitals. Sections have a small uppercase muted label with a 24px round area chip and a chevron, and open and close; the open or closed choice is remembered per person on the server. Items are 44px high, 10px radius. The open page is a solid brand gradient highlight with white text and the button shadow, which slides between items. Never a black or pill shaped highlight. |
| Top bar | Left: breadcrumb in muted text with the current page in bold ink. Right: search, help, notifications bell with a count badge, the person's initials and name with a menu. |
| Page header | A 44px round area icon chip, the title (24px, semibold), one line of plain explanation (muted, no wider than 48rem), and on the right the actions: any number of outline buttons and at most one solid button, the main action. |
| Record header | For a single record (a lead, a project, an order): a Back link above it, then a sticky bar under the top bar with the title, the status pill, one muted line (code, place, owner) and the actions on the right. Edit is the solid button. |
| Section card | White card, 14px radius, soft shadow. Heading is small uppercase muted text (13px in PAMAA, letter spacing 0.06em, semibold; a product with a higher type floor, such as BuildOS at 16px, uses its floor size and keeps the uppercase, spacing and weight), with an optional tag chip. Optional one line of help under it. Content is a field grid of 1 column on a phone and 2 or 3 columns from tablet. Optional footer row for the card's actions. |
| Field (read) | A small muted label above the value in ink. A missing value reads Not filled in in muted text, never a blank or a dash. |
| Stat tile | Label at the top left in muted text, a 32px round area icon chip at the top right, the number under the label (24px, semibold, tabular figures), an optional one line of helper text. The top edge is a 3px bar in the tile's colour, clipped by the card's corners: brand for normal, amber for waiting or at risk, red for late, green for done. The whole tile is the link. Tiles sit in an equal column grid with a 16px gap, and tiles in a row stretch to the tallest. |
| Status pill | Round, 1px border in the status line colour, tinted background, an icon and a word, 14px, medium weight. A pill that says something is late flashes softly once. |
| Table | Header cells small uppercase muted with letter spacing; rows have 10px vertical padding, a soft divider, and a soft brand tint on hover; a row that opens something is focusable and opens on Enter. On a phone each row becomes a card with each value under its column name. A table scrolls inside its card when it is wider than the card. |
| Empty state | Dashed brand tinted box, 14px radius, a 44px area icon chip, a bold one line title, one muted sentence saying what to do, and the action button if there is one. Never a bare line of grey text. |
| Notice | A white card with a 4px coloured left edge (amber for warnings, brand for rules and information), a bold one line title, and a short list. Several notes are one notice, never separate boxes. |
| Tabs | A row of text tabs on a bottom line, 44px high; the open tab has a 2px bottom line in the area colour and bold ink text. |
| Dialog | 14px radius, lift shadow, title, one line of explanation, content, and a footer with the cancel action on the left of the confirming action, right aligned. A destructive confirmation uses the danger button. |
| Toast | Bottom right, for saved and failed messages, never blocks the page. |
| Loading and error | Skeleton shapes that match the content, and an amber notice with Try again for errors. |

## 4. Buttons and links

One height, 44px. 18px side padding, 16px text, weight 500 or 600, 8px gap between icon and label.

| Kind | Look | Use |
|---|---|---|
| Solid | Brand gradient, white text, button shadow | The main action of a screen or card. At most one per area. |
| Outline | White, 1px brand border at 35 percent, brand text, soft brand fill on hover | Every other action. This is the default button. |
| Link | Brand text, underlined with a soft line, 44px tap area | Navigation inside text, Back links, View all. |
| Danger | Outline in red, and solid red only for the final confirming button | Delete, remove, cancel a booking. |
| Icon | Square 44px, outline or plain, with a tooltip and an accessible label | Toolbars. |

Pressed buttons move down 1px and scale to 98 percent. Focus is a 2px brand ring at 50 percent with a 1px
offset. Disabled is 50 percent opacity. No grey filled buttons, no black buttons, no buttons drawn as
text.

Fields and selects are 44px high, 10px radius, 1px field border, a brand ring on focus, and one dropdown
arrow on every system.

## 5. Page anatomy

Every screen is one of four shapes.

1. **List screen.** Page header (icon, title, one line, Add button), a search box and a Filters button
   on one row (the same height as the buttons), active filters as removable chips, optional stat tiles,
   then a table card or a card list, then the empty state when there is nothing.
2. **Record screen.** Back link, record header, then a grid of two columns: the main column (two thirds)
   holds section cards, the side column (one third) holds summary cards and change history. Tabs sit above
   the main column when a record has several areas. The side column is never empty and the main column is
   never narrower than the side column.
3. **Dashboard screen.** Page header, a row of stat tiles, then section cards in two balanced columns of
   natural height, each row of a list showing a title line, a muted second line, a status pill and an
   Open link, with a Go to card of the most used screens.
4. **Form or settings screen.** Page header, a single notice area at the top, then section cards each with
   a 2 column field grid, and a sticky footer with Save (solid) and Undo changes (outline).

## 6. Rules that keep it consistent

1. One h1 per page, drawn by the page header or the record header.
2. Section headings are the small uppercase style, card titles in the dashboards are the same style, and
   nothing else is used as a heading.
3. Status is always a pill. Money is always formatted the same way. Dates are always formatted the same way.
4. Each area keeps its colour and icon everywhere.
5. No page writes a radius, padding, shadow, font size or colour. Pages use tokens and the pieces.
6. A checking script fails the build when a page draws its own button, card, heading or colour.
7. Every screen is checked at 1440 pixels and 390 pixels wide: nothing is cut off, overlaps or scrolls
   sideways by accident.

## 7. For SellOS

1. Copy this document and the token file of BuildOS or PAMAA, and set SellOS's brand colours, area colours
   and icons.
2. Build the shared pieces in section 3 first, with a gallery page that shows each one.
3. Build every screen from them, using the four shapes in section 5.
4. Add the checking script from rule 6 on the first day, not at the end.
