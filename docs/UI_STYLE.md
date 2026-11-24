# SellOS UI style guide (SOS-UI-1, SOS-UI-2B)

> **Colours, radius, shadows, the shell and the nav pill are now defined in [`UI_STANDARD.md`](UI_STANDARD.md)** (24 November 2026: the shared BuildOS and PAMAA look, with the SellOS green as the accent only). The Pandya palette, cream page and dark shell described in the sections below are **superseded**; this file stays for the component list ("Copied from PAMAA"), the patterns and the checklist, and its colour tables are kept as history.

SellOS has PAMAA's layout and components in the **Pandya Realtors palette**. Three sources, each used for one thing:

| What | Source |
| --- | --- |
| Colours, radius, spacing | `docs/ui-reference/pandya-website-design-tokens.md` (copied from `~/iespl-baseline/pandya-website-design-tokens.md`) |
| Fonts and type scale | PAMAA (`~/iespl-bench/apps/pamaa_erp/frontend`, read only): Inter, 16px body, PAMAA's title sizes. **Not** the website's stangith or Figtree, and not its 20px body |
| Layout and components | PAMAA's shell, sidebar, top bar, page header, cards, badges, toasts, empty and error states (list in "Copied from PAMAA" below) |

The tokens are in `frontend/src/theme/ui-tokens.js` (data), `ui-tokens.css` (CSS variables and the self hosted Inter), `tokens.js`
(Tailwind theme, brand variables) and `frappe-ui-map.js` (frappe-ui's palette). `scripts/contrast.py` computes every ratio below.
Screenshot of PAMAA's sign in page: `docs/ui-reference/pamaa-sign-in.png`. The other PAMAA
patterns could not be photographed: that needs a PAMAA login, which this work must not create. Jayman compares the SellOS demo with
PAMAA at `pamaa-demo.localhost:8020` in their own browser.

## Colours

Primitives (the website's names): teal/900 `#002D2D`, teal/700 `#003C3C`, teal/500 `#004848`, gold/200 `#FFDC9C`, gold/500 `#E4B33C`,
cream/100 `#FFF2DC`, teal/700 at 25%.

| Use | Token | Value |
| --- | --- | --- |
| Page background | surface/cream | `#FFF2DC` |
| Sidebar and top bar | surface/dark | `#003C3C` |
| Text on the sidebar and top bar | text/onDark | `#FFDC9C` |
| Current sidebar item | surface/accent, text/accent | `#004848`, `#E4B33C` |
| Primary button | button/bg, text/button | `#003C3C`, `#E4B33C` |
| Secondary button | button/ghostBg, button/ghostBorder | teal/700 at 25%, `#002D2D` |
| Text on light | text/onLight | `#003C3C` |
| Links | teal/700, underlined | `#003C3C` |
| Cards and inputs | white, 1px teal/900 line at low opacity | see below |
| Dividers on dark | white at 15% (a quieter border/onDark: full gold/500 lines are too loud between menu items) | `rgba(255, 255, 255, 0.15)` |

**Jayman's call (approved 20 Nov 2026):** cards and inputs are white with a thin teal/900 line at low opacity, not a solid border. Cards use
20% (`--ui-line`), table row lines 10%. The website tokens have no input border. An input's edge must reach 3:1 against white (WCAG 1.4.11), and
teal/900 at 20% gives 1.5:1, so **inputs use the same teal/900 at 55%** (3.6:1). That 55% is the one number to change if the line should be
lighter; it lives in `ui-tokens.js` as `lines.field`.

### Added tokens (derived, because the website has none)

| Token | Value | Why |
| --- | --- | --- |
| text body | `#004848` (teal/500) | labels, secondary text |
| text muted | `#3F6767` | small print, table headings, breadcrumb; 5.7 on cream, 6.3 on white |
| faint | `#FFF8EE` | cream at 50% over white |
| subtle | `#F0E7D2` | teal/700 at 6% over cream (locked areas) |
| brand soft | `#EBEFEF` | teal/700 at 8% over white (hover, selected) |
| tag background | `#E1E9E8` | small tags, the neutral badge |

### Status colours (approved: success, warning, danger, info)

Each badge shows a word and an icon as well as a colour. Never colour alone.

| Tone | Ink | Background | Line | Icon |
| --- | --- | --- | --- | --- |
| success | `#0B5D3B` | `#DDEFDF` | `#8FC4A0` | circle-check |
| warning | `#7A4A00` | `#FFEBC0` | `#E4B33C` | triangle-alert |
| danger | `#A4281B` | `#FBE1DC` | `#E0958B` | circle-alert |
| info | `#1B5A78` | `#DCEAF2` | `#8DB6CC` | circle-dot |
| neutral (not a status; a badge with no tone) | `#003C3C` | `#E1E9E8` | teal/900 at 20% | circle-dashed |

Rule from the website: **never gold/500 text on gold/200** (1.5:1). gold/500 text is only for teal surfaces.

### Contrast, every pairing

Text needs 4.5:1, an input edge 3:1, decorative lines nothing. `FAIL` on the NEVER row is the point of that row.

| Pairing | Foreground | Background | Ratio | Needs | Result |
| --- | --- | --- | --- | --- | --- |
| text/onDark on surface/dark (sidebar, top bar) | #FFDC9C | #003C3C | 9.3 | 4.5 | pass |
| text/accent on surface/dark | #E4B33C | #003C3C | 6.3 | 4.5 | pass |
| text/accent on surface/accent (current sidebar item) | #E4B33C | #004848 | 5.4 | 4.5 | pass |
| text/onDark on surface/accent | #FFDC9C | #004848 | 7.9 | 4.5 | pass |
| text/onDark on sidebar hover (surface/accent at 50%) | #FFDC9C | #004242 | 8.6 | 4.5 | pass |
| text/onLight on surface/cream (page) | #003C3C | #FFF2DC | 11.1 | 4.5 | pass |
| text/onLight on white (cards, inputs) | #003C3C | #FFFFFF | 12.3 | 4.5 | pass |
| text/onLight on surface/gold | #003C3C | #FFDC9C | 9.3 | 4.5 | pass |
| text/button on button/bg (primary button) | #E4B33C | #003C3C | 6.3 | 4.5 | pass |
| text/onLight on button/ghostBg over white (secondary button) | #003C3C | #BFCECE | 7.6 | 4.5 | pass |
| text/onLight on button/ghostBg over cream | #003C3C | #BFC4B4 | 6.9 | 4.5 | pass |
| link teal/700 on cream | #003C3C | #FFF2DC | 11.1 | 4.5 | pass |
| link teal/700 on white | #003C3C | #FFFFFF | 12.3 | 4.5 | pass |
| input border teal/900 at 55% on white (field) | #738C8C | #FFFFFF | 3.6 | 3.0 | pass |
| card border teal/900 at 20% on cream (decorative) | #CCCBB9 | #FFF2DC | 1.5 | 1.0 | pass |
| NEVER: text/accent gold/500 on surface/gold gold/200 | #E4B33C | #FFDC9C | 1.5 | 4.5 | FAIL |
| success ink on success background (badge) | #0B5D3B | #DDEFDF | 6.6 | 4.5 | pass |
| success ink on white | #0B5D3B | #FFFFFF | 7.9 | 4.5 | pass |
| success ink on cream | #0B5D3B | #FFF2DC | 7.2 | 4.5 | pass |
| success line on success background (border, decorative) | #8FC4A0 | #DDEFDF | 1.7 | 1.0 | pass |
| warning ink on warning background (badge) | #7A4A00 | #FFEBC0 | 6.4 | 4.5 | pass |
| warning ink on white | #7A4A00 | #FFFFFF | 7.5 | 4.5 | pass |
| warning ink on cream | #7A4A00 | #FFF2DC | 6.8 | 4.5 | pass |
| warning line on warning background (border, decorative) | #E4B33C | #FFEBC0 | 1.7 | 1.0 | pass |
| danger ink on danger background (badge) | #A4281B | #FBE1DC | 5.8 | 4.5 | pass |
| danger ink on white | #A4281B | #FFFFFF | 7.2 | 4.5 | pass |
| danger ink on cream | #A4281B | #FFF2DC | 6.6 | 4.5 | pass |
| danger line on danger background (border, decorative) | #E0958B | #FBE1DC | 1.9 | 1.0 | pass |
| info ink on info background (badge) | #1B5A78 | #DCEAF2 | 6.1 | 4.5 | pass |
| info ink on white | #1B5A78 | #FFFFFF | 7.6 | 4.5 | pass |
| info ink on cream | #1B5A78 | #FFF2DC | 6.8 | 4.5 | pass |
| info line on info background (border, decorative) | #8DB6CC | #DCEAF2 | 1.8 | 1.0 | pass |

## Type, spacing, radius, shadow

* **Font:** Inter 400, 500, 600, 700, **self hosted** as WOFF2 (`frontend/src/theme/fonts/`, from Frappe's copy, SIL Open Font License 1.1) with
  `font-display: swap`. No request goes to Google Fonts.
* **Type scale (PAMAA's):** title 24px/1.25, 600; card heading 13px, 600, uppercase, 0.06em tracking; small 14px; body 16px; stat number 24px, 600, tabular figures.
* **Spacing (the website's):** xs 4, sm 8, md 14, lg 24, xl 48 (`gap-ui-md`, `p-ui-lg`). Card padding 14px, 24px from 640px. Controls are at least 44px tall and wide (PAMAA's touch size). The website's page margin of 69px is for a 1728px canvas; the app uses the scale.
* **Radius (the website's):** 8px for buttons and inputs (`rounded-input`), 16px for cards, menus and dialogs (`rounded-card`), full for chips and badges.
* **Shadows:** PAMAA's soft two layer card and lift shadows, tinted teal/900 instead of grey. No button shadow, no gradients: the website keeps gradients to photo shapes.
* **Motion:** 120, 180, 250 ms, off under `prefers-reduced-motion`. **Icons:** Lucide.

## Company brand colour

`CompanyBrand` and `applyCompanyTheme` (session.js) keep the per company override. The Pandya palette is the default. A company's `brand_color`
replaces the sidebar and top bar band and the primary button (`--sos-brand`); the current item and button hover use a lighter mix (`--sos-brand-mid`);
text on the band switches to white or near black by luminance so it stays readable on any colour (`--sos-on-brand`, `--sos-on-brand-accent`).
The rest of the palette (cream page, cards, status colours) does not change.

## frappe-ui

frappe-ui takes its colours from the Tailwind config. `frontend/tailwind.config.js` remaps them: `frappe-ui-map.js` replaces its semantic
variables (`--surface-gray-7` is button/bg, `--text-ink-white` is text/button, `--outline-gray-2` is the input line, the green, amber, red and
blue badge variables are the four status tones) and its static ramps (gray, blue, green, red, orange, amber, cyan). A frappe-ui Button, Input,
Select, Badge, Dialog or Toast picks the Pandya palette up with no extra class. Components in `frontend/src/components` wrap frappe-ui:
`AppButton` (Button), `FormField` (FormControl, always with a label), `StatusBadge` (Badge). Dialogs use frappe-ui's `Dialog` directly.

frappe-ui's Select is a button that opens a list, not a native `<select>`. `cy.select()` is overwritten in `cypress/support/commands.js` to click the trigger and the option, so specs read the same.

## Copied from PAMAA

PAMAA imports only `TextInput` and `Password` from frappe-ui; its other pieces are plain HTML with its own Tailwind classes. SellOS builds the same
pieces on frappe-ui components. The decision for each, with the file in `frontend/src/components` (or `src`):

| PAMAA piece | Decision | SellOS file | Why |
| --- | --- | --- | --- |
| Shell and layout (`AppShell.vue`) | adapt | `AppShell.vue`, `viewport.js` (copied as is), `shell.js` | Same frame. The sidebar and bottom bar switch by CSS at 1024px so both stay in the page; no page fade, no area colours |
| Sidebar (`AppSidebar.vue`) | adapt | `AppSidebar.vue` | Menu comes from `personas.js`, grouped by area; sections stay open (the longest menu has 11 places); the highlight does not slide; dark surface |
| Bottom bar and More drawer | adapt | `BottomBar.vue` | Four places and More; the rest in the drawer |
| Top bar with breadcrumbs (`AppTopBar.vue`) | adapt | `AppTopBar.vue` | Breadcrumb from the route title, search, bell, user menu. Role switch, offline badge and waiting-to-send are left out (SellOS has none of them) |
| Search (`GlobalSearch.vue`) | adapt | `SearchDialog.vue` | PAMAA searches many record types; SellOS has one searchable list, so a frappe-ui Dialog sends the text to Leads as `?q=` |
| Help (`HelpPanel.vue`) | **skip** | none | It shows PAMAA's own guide content from `help.js`; SellOS has no help content. Add one when there is something to say |
| Page header (`ListHeader.vue`) | copy | `PageHeader.vue` | Title, one line, actions on the right. `titleTestid` names the title's test id (Home welcome) |
| Stat card (`StatCard.vue`) | adapt | `StatCard.vue` | Without the count-up and area colours. `valueTestid` names the number's test id (Today counts) |
| List card (`.pamaa-card` + `DataTable.vue`) | adapt | `ListCard.vue` | PAMAA has no list card component. The Leads rows keep their links and test ids, so PAMAA's table is not copied; phone card rows follow later with SOS-UI-3 |
| Filter bar | **new** | `FilterBar.vue` | PAMAA has none; its screens place inputs by hand. A card, a grid of labelled fields, Apply and Clear |
| Form field (`AccessField.vue`) | adapt | `FormField.vue` | On frappe-ui `FormControl`; label always visible, red `*`, hint |
| Badge (`StatusPill.vue`) | adapt | `StatusBadge.vue` | On frappe-ui `Badge`, word and icon, four status tones plus neutral; no flash |
| Button (`.pamaa-button`) | adapt | `AppButton.vue` | On frappe-ui `Button`: primary, secondary, danger |
| (checkbox) | **new** | `AppCheckbox.vue` | frappe-ui's Checkbox puts every attribute on its wrapper and its input, so a test id would exist twice; this wrapper keeps it on the input only |
| (file chooser) | **new** | `FileField.vue` | frappe-ui's FormControl has no file input. The one native file input lives in the shared folder, with a visible label and the Pandya tokens; `data-testid` sits on the input (SOS-UI-3B) |
| Dialog | **not in PAMAA** | frappe-ui `Dialog` | Used directly (search) |
| Toast (`ToastHost.vue`) | adapt | `ToastHost.vue`, `shell.js` | Same host and `showToast`; tones success, warning, danger, info |
| Empty state (`EmptyState.vue`) | copy | `EmptyState.vue` | |
| Report table (`ReportTable.vue`) | new | `ReportTable.vue` | SOS-P5-03: one row per thing and one column per figure, each column with a unit (number, rupees, seconds or text). Totals per company use it |
| Report panels (`ReportPanels.vue`) | new | `ReportPanels.vue` | SOS-P5-03: the panels that wait for data another task builds. A waiting panel shows an `EmptyState` with its message; a live one shows its stat cards and a `ReportTable` |
| Load error, loading skeleton | copy | `LoadError.vue`, `LoadingSkeleton.vue` | Rows only |

## Patterns

**Shell.** Sidebar 240px from 1024px wide, surface/dark, text/onDark, items 44px tall with an 8px radius, the current one on surface/accent in text/accent, sign out at the foot. Top bar at least 61px, surface/dark, breadcrumb on the left, search, bell and user menu on the right. Below 1024px: a bottom bar (four places and More) and the brand in the top bar. Main has 14px side padding, 24px from 640px.

**Page header.** Title 24px/600, one line of text, actions on the right. One primary button per screen.

**Cards.** White, 16px radius, 1px teal/900 line at 20%, card shadow, an uppercase 13px heading. **Tables and lists:** inside a card, row lines at 10%, row hover on brand soft, shimmer rows while loading.

**Forms.** Label above every field (16px, teal/500, red `*` if required), 44px field, 8px radius, 1px line at 55%, focus ring in the brand colour. Hints and errors 14px under the field; errors in the danger ink. One column on a phone, two from 640px, four from 1280px in a filter bar.

**Buttons.** 44px, 8px radius, 16px/500. Primary: button/bg with text/button. Secondary: button/ghostBg with a button/ghostBorder line. Disabled 50%.

**Badges, empty and error states, toasts.** As PAMAA, in the palette above.

## Checklist for a new screen

1. Colours, radius, spacing and fonts come from the tokens. No colour, size or font written by hand.
2. It sits in the shell and starts with a `PageHeader`.
3. Content is in `ListCard` or `.ui-card`.
4. Every control is a frappe-ui component (`AppButton`, `FormField`, `StatusBadge`, `Dialog`); every field has a label.
5. A list with no rows shows `EmptyState`, a failed load `LoadError` with Try again, a save or failure a toast.
6. Money shows in rupees with Indian grouping (`₹50,00,000`).
7. Keep every `data-testid`.

Screens not yet moved (everything except Leads and the lead page) still use the older `.btn`, `.field` and `.ui-card` classes. Those now take the Pandya
colours from the tokens, and the old `accent` colour is the danger red until SOS-UI-3 moves them.
