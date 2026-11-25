# SellOS design system

SellOS's copy of the one design system of BuildOS, PAMAA and SellOS. The source is `docs/DESIGN_SYSTEM_SOURCE.md`
(version 1, 24 November 2026); read it first. This file is the same system with SellOS's brand colours, areas and
icons filled in. **If this file and the source disagree, the source wins.** `docs/UI_STANDARD.md` keeps the contrast
table, the public pages and the screenshots; where it disagrees with this file, this file wins (the list is at the end).

**The rule.** A page is assembled from the shared pieces in `frontend/src/components`. If a page needs something the
pieces do not offer, the piece is extended first. Pages never style their own headings, cards, buttons, figures or
status words. `scripts/check_design_system.py` fails the build (pre-commit and CI) when one does.

## 1. Tokens

One token file, `frontend/src/theme/ui-tokens.js` (`designTokens`, `radius`, `shadows`, `areas`), repeated as CSS
variables in `ui-tokens.css` and as the Tailwind theme (`theme/tokens.js`). `sellos/tests/test_design_tokens.py` keeps
the three in step. A page never writes a value.

| Token | Value | Name |
|---|---|---|
| Card radius | 14px: cards, panels, dialogs, menus that open from a button, boxed notes | `rounded-card`, `--radius-card` |
| Control radius | 10px: buttons, fields, selects, sidebar items, small rectangular chips | `rounded-control`, `--radius-control` |
| Round | fully round: icon badges, avatars, status pills, count badges | `rounded-round`, `--radius-round` |
| Touch height | 44px minimum for every button, field, select and menu row | `min-h-touch` |
| Card padding | 16px, 20px from 640px | `.ui-card` |
| Gap between stacked cards | 16px | `gap-ui-md` |
| Field grid gap | 20px across, 16px down | `FieldGrid` |
| Page margin | 16px on a phone, 24px from 640px, content at most 1440px | `.ui-content` |
| Card shadow | `0 1px 2px rgba(17,24,39,0.04), 0 6px 20px -8px rgba(17,24,39,0.10)` | `shadow-card` |
| Lift shadow | `0 2px 4px rgba(17,24,39,0.05), 0 14px 32px -12px rgba(17,24,39,0.18)` | `shadow-lift` |
| Button shadow | `0 1px 2px rgba(dark brand,0.25), 0 4px 12px -4px rgba(brand,0.4)`, follows a company's brand colour | `shadow-button` |
| Motion | 120ms fast, 180ms base, 250ms slow, `cubic-bezier(0.16, 1, 0.3, 1)`, all off under reduced motion | `--ui-ease` |
| Font | Inter, then system fonts (self hosted) | |
| Type floor | 14px small print (`text-xs`), 16px for everything people read for more than a word (`text-base`). Never lower. Title 24px/600, card heading 13px uppercase with 0.06em spacing, stat 24px tabular | `ui-text-*` |

**Colour.** Neutrals, status colours and the contrast pairings are unchanged from `docs/UI_STANDARD.md` (ink `#1D222B`,
body `#3F4A5C`, muted `#525F78`, line `#DDE2EC`, line soft `#EBEEF4`, field `#778399` which is 3.8:1 where the source's
`#8A96AD` is 3.0:1, page `#F4F5F7`, faint `#F8F9FB`; success, warning, danger, info and neutral each with ink, background
and line). **Brand** is SellOS green: `#0F4C35`, mid `#2A7A5A`, dark `#0A3626`, tint `#E3F0EA`. The solid button and the
open menu item use the gradient from brand to mid. A company's `brand_color` still replaces it at runtime.

### Areas

Each area has one accent, one soft tint, one dark ink and one icon, defined once (`areas` in `ui-tokens.js`), taken from
SellOS's own palette, and used for the sidebar section chip, the page header icon, the card top edge, the stat figures and
the empty state. The page sets `data-area` on its shell; the pieces read `--area-accent`, `--area-soft`, `--area-ink`.

| Area | Accent | Soft | Ink | Icon | Places |
|---|---|---|---|---|---|
| Leads and Sales | `#0F4C35` (brand) | `#E3F0EA` | `#0A3626` | `lucide-users` | Leads, Sellers, Mandates, Deals, Import leads; the partner's firm, register and leads; the client's pages; Home |
| Calls and WhatsApp | `#1A6175` (info) | `#EEF8FA` | `#0E3E4C` | `lucide-phone-call` | Call queue, WhatsApp, Site visits, Call lists, Response alerts |
| Inventory | `#8A4B00` (warning) | `#FEF8ED` | `#5C3200` | `lucide-building` | Projects and listings, Import inventory |
| Money | `#08724E` (success) | `#ECFAF5` | `#054D34` | `lucide-hand-coins` | Commission, earnings, every report |
| Company | `#3F4A5C` (body) | `#F0F3F9` | `#1D222B` | `lucide-building-2` | Users, Support access, Telephony, WhatsApp setup, Teams, Assignment, Channel partners, Companies |

## 2. The shared pieces

All in `frontend/src/components`; the gallery (`/sellos/gallery`, any signed in role, not in the menu) shows every one in every
state, and in each area's colours.

| Piece | Component | Notes |
|---|---|---|
| App shell | `AppShell` | 240px sidebar, 61px sticky top bar, `.ui-content` page area; bottom bar with a More drawer on phone and tablet |
| Sidebar | `AppSidebar` | square logo mark, area chips on the section labels, 44px items, solid brand highlight that slides, open or closed saved per person on the server |
| Top bar | `AppTopBar` | breadcrumb (current page bold), search, help, bell with count, initials and name with a menu |
| Page header | `PageHeader` | 44px round area icon chip, title (24px), one line (muted, at most 48rem), outline actions and at most one solid |
| Record header | `RecordHeader` | Back link, sticky bar with title, status pill, one muted line, actions; Edit is solid |
| Section card | `SectionCard` | card with the small uppercase heading, optional tag and help, a `FieldGrid`, optional footer |
| Timeline | `Timeline` | a vertical history: a dot per event, strong title, muted time line and notes (the lead's stage history) |
| Disclosure | `Disclosure` | a card closed until opened, for a rare action kept at the bottom of a page (merge a duplicate client) |
| Read field | `ReadField` | muted label, ink value, a missing value reads "Not filled in" |
| Stat tile | `StatCard` / `KpiStrip` | 3px top bar in the tile's colour, 32px round chip, 24px tabular number, helper line; the whole tile is the link |
| Status pill | `StatusBadge` | round, 1px line, tint, icon and word, 14px |
| Table | `DataTable` | uppercase muted header, 10px row padding, soft divider, hover tint, Enter opens; phone rows become cards; `dense` tightens the cell padding for a wide table that must fit 1440 |
| Empty state | `EmptyState` | dashed tinted box, 44px area chip, bold title, one muted sentence, the action |
| Notice | `Notice` | white card, 4px coloured left edge, bold title, a short list; several notes are one notice |
| Tabs | `PageTabs` | 44px text tabs on a line; open tab has a 2px area line and bold ink |
| Dialog | `Dialog` (frappe-ui) | 14px, lift shadow, cancel on the left of the confirming action |
| Toast | `ToastHost` | bottom right, never blocks |
| Loading and error | `LoadingSkeleton`, `LoadError` | skeletons shaped like the content; amber notice with Try again |
| Buttons | `AppButton` | solid (`primary`), outline (default), link, danger (outline, `confirm` for solid), icon |
| Fields | `FormField`, `MoneyField`, `AppCheckbox` | 44px, 10px radius, brand ring on focus, one arrow |
| Filter row | `FilterBar` | search and Filters on one row, removable filter chips |
| Form footer | `FormFooter` | sticky Save (solid) and Undo changes (outline) |
| Drawer | `FormDrawer`, `FormSection` | right side drawer with a sticky footer |

## 3. Screen shapes

Every page is one of four shapes (`PageTemplate` with a `shape`):

1. **List** (Leads, Sellers, Mandates, Deals, Commission, Call queue, WhatsApp, Site visits, Inventory, Users): page header; search and Filters on one row;
   removable filter chips; stat tiles where useful; table card; empty state.
2. **Record** (lead, seller, mandate, deal, project): Back link; record header; two thirds and one third columns; the side
   column is never empty and the main column is never narrower; tabs above the main column when a record has several areas.
3. **Dashboard** (Home and every role's home): stat tiles; two balanced columns of section cards, each row a title line, a muted
   line, a status pill and an Open link; a Go to card.
4. **Form or settings** (company settings, setup wizard, Import leads, Import inventory): one notice area; section cards with a
   two column grid; sticky footer with Save and Undo changes.

## 4. Rules

1. One h1 per page, drawn by the page header or the record header.
2. Headings are the small uppercase style only; a page writes no `<h1>` to `<h6>`.
3. Status is always a pill. Dates are `24 Nov 2026, 11:44` (`formatWhen`) everywhere. A missing value reads "Not filled in".
   Money follows rule 8.
4. Each area keeps its colour and icon everywhere.
5. No page writes a radius, padding, shadow, font size, font weight or colour: pages use layout utilities (flex, grid, gap, margin,
   width, overflow), the pieces and the named text roles `ui-text-body`, `-secondary`, `-strong`, `-small`, `-muted`, `-error`,
   `-warning`, `-success`.
6. `scripts/check_design_system.py` runs in pre-commit and in CI. `docs/design-system-backlog.txt` lists the pages that still fail while
   the pass is under way; it only shrinks and ends empty.
7. Every screen is checked at 1440 and 390 wide, for all four roles, for cut off content and sideways scroll
   (`cypress/integration/visual/walkthrough.cy.js`).

8. **Money.** One format everywhere, written only in `frontend/src/format.js`: `Rs`, never the rupee sign, never paise.
   - `formatBudget` is the default, for every figure read at a glance (a budget, a price, a total, a spend): `Rs 2.3 crore`,
     `Rs 95 lakh`, and below a lakh the full amount with Indian grouping, `Rs 45,000`.
   - `formatMoney` is for an amount that must be exact: a payout, an invoice, a cost sheet line, a commission split. It is the full
     figure with Indian grouping, `Rs 12,50,000`, rounded to the rupee.
   - A page never formats money itself. `scripts/check_design_system.py` fails on the rupee sign, `Intl.NumberFormat`, a currency
     style, fraction digits, a paise argument and a rupee figure typed into a file, anywhere under `frontend/src` but `format.js`
     (and the typing field `MoneyField`). There is no backlog for it.

## 5. What replaced what

Rules of `docs/UI_STANDARD.md` and of the first layout pass (24 November 2026) that this file replaces, because the source
document says otherwise:

* "One 14px radius for every element" became card 14px, control 10px, round for pills, badges, avatars and icon chips.
* The current menu item as a 14px pill in the flat brand colour became a solid brand gradient highlight, 10px radius, with the
  button shadow, which slides between items. Sidebar groups are the five areas (Leads and Sales, Calls and WhatsApp, Inventory, Money,
  Company) with an area chip, not Work, Sales, Inventory, Data and Company.
* The default button is the outline (brand border at 35 percent, brand text), not the grey ghost; the solid button has the brand
  gradient and the button shadow; danger is an outline in red; a disabled button is 50 percent opacity, not dashed.
* Card padding 16px and 20px from 640px (was 14px and 24px); gap between cards 16px (was 14px); page margin 16px and 24px with content at
  most 1440px; focus is a 2px brand ring at 50 percent with a 1px offset.
* Pages no longer write text colours, sizes, weights, radii, paddings or card chrome; they use the pieces and the named text roles.
