# SellOS UI standard (UI_STANDARD)

> **Superseded in part by `docs/DESIGN_SYSTEM.md` (25 November 2026).** The radius, button, sidebar, card padding and page margin rules below were replaced by the shared design system; `DESIGN_SYSTEM.md` section 5 lists exactly which. The contrast table, the public pages and the screenshots below still apply.

The one visual system of SellOS, BuildOS and PAMAA. It replaces the cream page and dark green shell of SOS-UI-2B (`docs/UI_STYLE.md`
keeps the component list and the screen checklist; this file owns every colour, size and shadow). Requested by Jayman on 24 November 2026.

**What is shared and what is SellOS's own.** BuildOS (`~/iespl-baseline/buildos-reference/frontend`, `tailwind.config.js`, `src/theme/tokens.js`,
`src/index.css`, `AppShell.vue`) and PAMAA (`~/iespl-bench/apps/pamaa_erp/frontend`, `src/tokens.js`, `src/index.css`), both read only, come from the same
Atomic design system: the same neutrals, the same Inter, the same soft shadow, the same status colours, the same round controls. They differ only
in the accent (BuildOS blue to teal to green, PAMAA indigo). SellOS takes every shared value as it is and keeps one colour of its own, the SellOS
green of `docs/BRAND.md`, **as the accent only**: the primary button, the current menu pill, links, the focus ring and the selected tint. A company's
`brand_color` still replaces it at runtime (`session.js`, `applyCompanyTheme`).

The tokens are data in `frontend/src/theme/ui-tokens.js`, repeated as CSS variables in `ui-tokens.css`, read by `tokens.js` and `tailwind.config.js`, and
remapped for frappe-ui in `frappe-ui-map.js`. Never write a colour, size or shadow by hand on a page. `scripts/contrast.py` computes every ratio below.

## Tokens

| Token | Value | BuildOS | PAMAA | Used for |
| --- | --- | --- | --- | --- |
| Page background | `#F4F5F7` | neutral-grey `#F4F5F7` | tint-from `#F4F5F7` | the page, behind every card |
| Card | white, 1px `#DDE2EC`, shadow card | white, border `#D9D9D9` at 70%, shadow card | white, border `#DDE2EC`, shadow card | every panel, list, form and stat |
| Card shadow | `0 1px 2px rgba(17,24,39,.04), 0 6px 20px -8px rgba(17,24,39,.10)` | the same | the same | cards; the lift shadow `0 2px 4px rgba(17,24,39,.05), 0 14px 32px -12px rgba(17,24,39,.18)` when a card is a link and is pointed at |
| Accent | `#0F4C35` (hover `#0A3626`, mid `#2A7A5A`, tint `#E3F0EA`) | primary `#323CE9` | indigo `#323CE9` | SellOS only: primary button, menu pill, links, focus ring, selected tint |
| Ink | `#1D222B` | neutral-900 | ink | text, strong lines |
| Body | `#3F4A5C` | neutral-700 | body | labels, menu text |
| Muted | `#525F78` | neutral-500 family | muted | small print, table headings, breadcrumb |
| Line | `#DDE2EC` / soft `#EBEEF4` | neutral-200 | line, line-soft | card edge, top bar, table rows |
| Field edge | `#778399` | neutral-400 `#8A96AD` | field `#8A96AD` | input border. PAMAA's `#8A96AD` is 3.0:1 on white and misses the 3:1 of WCAG 1.4.11, so SellOS darkens it a step (3.8:1) |
| Radius | ONE token, `--radius: 14px`, for cards, panels, inputs, selects, buttons, menus, drawers and modals; a status badge is a full pill (`--radius-pill`) | 10px | card 14px, control 10px | see Radius below |
| Spacing | 4, 8, 14, 24, 48px (`ui-xs` to `ui-xl`); control height 44px | 4px unit, gutter 16/20px | 44px touch | gaps and padding. Page side padding 14px, 24px from 640px |
| Font | Inter 400/500/600/700, self hosted | Inter | Inter | everything |
| Type scale | title 24/1.25 600; card heading 13px 600 uppercase 0.06em; body 16/1.6; small 14; stat 24/2rem 600 tabular | 26/22/17/15/13/12/11/10 | title 24, heading 13 | PAMAA's scale: 16px body is kept for phones |
| Motion | 120, 180, 250 ms, off under reduced motion | 150 to 160ms | the same | |

## Components

The page template, table, drawer, tabs, sidebar and lead page have their own sections below (Radius to Information hierarchy).

* **Shell.** A white sidebar 240px wide from 1024px (a bottom bar with four places and More below it), a white top bar at least 61px tall with a 1px bottom
  line, breadcrumb on the left, search, bell and user menu on the right (the title and the actions of a page are never in the top bar). The company name and an initial tile sit at the top of the sidebar.
* **Nav active pill.** The current menu item is a full-radius pill filled with the accent, white bold text and the card shadow (`.ui-pill-active`);
  the other items are `#3F4A5C` text with a `brand-soft` hover (`.ui-pill-hover`). Every item has a Lucide icon (`navIcons.js`), 16px, before the label.
  Section headings are 13px uppercase muted. BuildOS uses a near black pill and PAMAA a brand gradient; SellOS uses its accent, flat.
* **Cards.** `ListCard` and `.ui-card`: white, the one radius, 1px line, card shadow, padding 14px (24px from 640px), an uppercase 13px muted heading.
  `StatCard`: label, 24px number, a one line caption and an icon chip in a status tint.
* **Table.** Inside a card. A header row on faint (`#F8F9FB`) with 12px uppercase muted headings and a line under it, rows with `#EBEEF4` lines, row hover on the
  accent tint, clickable rows are links. On a phone each row becomes a card (BuildOS `bos-stack-table`).
* **Badge.** `StatusBadge`: a full-radius pill with a 1px tone line, the tone background, the tone ink, 12px/500, an icon and a word. Tones: success `#08724E`
  on `#ECFAF5`, warning `#8A4B00` on `#FEF8ED`, danger `#BE3910` on `#FEF0EC`, info `#1A6175` on `#EEF8FA`, neutral `#3F4A5C` on `#F0F3F9`. Never colour alone.
* **Form input.** `FormField`: the label above (16px, body, red `*` when required), a 44px field, the one radius, 1px `#778399` line, white fill, 16px text;
  focus is the accent edge and a 3px accent ring at 18%. Hints and errors are 14px under the field; errors in the danger ink. Checkboxes are accent boxes with a white tick.
* **Buttons.** 44px, the one radius, 16px/500, no shadow. Primary: accent fill, white text, one per screen. Secondary: white with a `#C9D0DD` edge, accent tint on hover. Danger: the red solid. Disabled is dashed on the subtle fill.
* **Skeleton loader.** `LoadingSkeleton`: rows of shimmer bars in the shape of a list, or (`variant="cards"`) a row of stat tiles in the shape of the
  stat cards. The shimmer is `rgba(17,24,39,.07)` to `.03`, 1.3s, off under reduced motion. Never a bare "Loading".
* **Empty state.** `EmptyState`: a dashed box on the subtle gradient, a 44px icon chip in the accent tint, a title, one line and an optional action.

## Radius

One token, `--radius: 14px` (`ui-tokens.css`, `radius.DEFAULT` in `ui-tokens.js`), for every card, panel, input, select, button, dropdown menu, drawer
and modal. Tailwind's `rounded` is that token; `rounded-t`, `rounded-b`, `rounded-l`, `rounded-r` and `rounded-none` follow it. Every sized name
(`rounded-sm` to `rounded-3xl`) is mapped to the same value, so frappe-ui's own components match. The only other radius is `rounded-pill`
(`--radius-pill`, full) on a **status badge**. A page never writes `rounded-card`, `rounded-input`, `rounded-badge`, `rounded-lg`, `rounded-full`, an
arbitrary `rounded-[..]` or a `border-radius` of its own. `sellos/tests/test_ui_radius.py` fails the build on a source file that does, and
`cypress/integration/frontend/ui_radius.cy.js` fails on any rendered element of any role's pages, the New lead drawer or the open filters that
is drawn with another radius.

## Page template

Every page, without exception, is built from `PageTemplate` (`frontend/src/components/PageTemplate.vue`) in this order:

1. **Top bar.** The shell's: breadcrumb on the left, search, bell and user menu on the right. Nothing of the page is in it.
2. **Page header card** (`PageHeader`, slot `header`): icon, title (24px, the biggest text on the page), one line of purpose, the actions on the
   right. Secondary actions first, the **one primary action** (`AppButton variant="primary"`) last, on the far right.
3. **KPI strip** (`KpiStrip`, slot `kpis`): at most four `StatCard`s, each a label, a number and a one line caption. A fifth is dropped.
4. **Filter row** (`FilterBar`, slot `filters`): ONE row. The search box first, then compact dropdowns (`FormField compact`: no stacked label, the
   first choice names the filter, such as "Any stage"), a **More filters** button for the rest (the panel opens under the row, and by itself when a
   bookmarked view already uses one) and **Clear**, shown only while a filter or the search is on.
5. **Main content** (default slot): a `DataTable`, or a board. 6. **Right rail** (slot `rail`): "Go to" links, on dashboards (Home) only.

A page with no list (a setup page, a form page) keeps the header card and puts its fields in headed sections (`FormSection`) inside `.ui-card`s.

## Tables

`DataTable` is the one table: a header band (`#F8F9FB`, 14px uppercase muted headings), row dividers (`#EBEEF4`), sortable columns (click a heading;
`aria-sort` is set), a sticky header inside a scrolling card, status pills (`StatusBadge` in a cell slot), a row action menu (`RowMenu`, a kebab that
opens a frappe-ui dropdown), pagination ("Showing 1 to 25 of 60", Previous and Next), and designed loading (`LoadingSkeleton`) and empty
(`EmptyState`) states. A clickable row opens its record; the primary column is a real link. On a phone each row is a card. Sorting and paging are
done on the rows the page already loaded, so no API call changes.

Leads columns: checkbox, name (the phone number sits under it once the list call returns one), project interest, source, stage, assigned agent,
budget, consent, last activity, next follow up, flags. Sellers, Mandates, Deals, Commission payouts, Call queue, Site visits, WhatsApp
conversations, Inventory units and Users use the same table.

## Bulk actions

The reassign controls are a `BulkBar`, and it exists only while one or more rows are selected: "N selected", the actions, and Clear selection.
The header checkbox of a `DataTable` selects every row of the list, on every page.

## Forms

Nothing is an open form under a list. "New lead", "Record a deal", "Add mandate" and the like open in a right side `FormDrawer`: a title and one
line, fields in headed `FormSection`s (two columns from 768px, one on a phone), and the **primary and Cancel buttons in a sticky footer**. Escape,
the close button and the overlay close it; the first field is focused on opening.

## Lead detail

A summary header card: the name, the stage pill, the consent pill, the phone, the assigned agent, and the Call, WhatsApp and Archive actions; the
next follow up sits under it. Then tabs (`PageTabs`): **Overview** (stage, merge), **Requirements** (the requirements, matching units, shortlists),
**Activity** (log an activity or a follow up, and the timeline), **Calls and WhatsApp** (log a call, the calls on the timeline, a link to WhatsApp),
**Site visits** (book a visit, the visits on the timeline) and **Deals** (the booking panel). `?tab=activity` opens a tab. The right rail, on every
tab, holds the assignment and the consent evidence.

## Sidebar

Home on its own, then collapsible groups, each with an icon and a small caps label, whose open or closed state is remembered in the browser
(`sellos.nav.groups`); the group holding the current page is always open. **Work**: Leads, Call queue, Site visits, WhatsApp. **Sales**: Sellers,
Mandates, Deals, Commission. **Inventory**: Projects and listings, Import inventory. **Data**: Import leads. **Company**: Users, Support access (and the
settings pages the Company Admin already has). **Reports**, **Platform**, **Partner** and **Your account** group the other roles' places. A role sees only
its own links and groups (`personas.js`). Call queue and WhatsApp carry a count badge (`navCounts.js`): WhatsApp counts the open conversations whose
last message is the person's, from the conversation list the app already reads; the Call queue badge shows the queue's total once the queue has
loaded (the queue call logs the numbers it shows, so the sidebar does not ask for it by itself).

## Information hierarchy

On every page the most important thing is the biggest and first: the title, then the KPI numbers, then the table. Text uses only this scale: **title**
24px/600, **card heading** 13px uppercase 600, **body** 16px, **small** 14px (`text-xs`: captions, badges, table headings), **stat** 24px tabular. No
other size is written on a page. **Dates** read `24 Nov 2026, 11:44` (`formatWhen`, `formatDateTime`, `formatDate`); **money** reads `Rs 12,50,000`
(`formatMoney`: Indian digit grouping).

## Public pages

The two pages a customer sees before the app have the same look and are not part of the Vue app, so they carry the tokens by hand, the only places that may:

* **Sign in** (Frappe's `/login`): `sellos/public/css/sellos_login.css`, scoped to `.for-login`. The neutral page, one white 14px card with the card shadow, the SellOS tile in the accent, 44px fields with the `#778399` line and a 10px radius, a solid accent button, focus as the soft accent ring. How sign in works is unchanged.
* **Enquiry** (`/enquiry`, `sellos/www/enquiry.html`): the same, in the template's own `<style>` (the page stands alone). Success and refusal notices use the success and danger tones.
* **Inter** for both is `sellos/public/fonts/*.woff2` (400, 500, 600), the same files as `frontend/src/theme/fonts`, SIL Open Font License 1.1.
* `cypress/integration/frontend/ui_style.cy.js` checks both pages' page colour, card, radius, field height and button colour.

## Contrast, every pairing

Text needs 4.5:1, an input edge 3:1, decorative lines nothing. Output of `python3 -I scripts/contrast.py`.

| Pairing | Foreground | Background | Ratio | Needs | Result |
| --- | --- | --- | --- | --- | --- |
| text on page (ink on neutral page) | #1D222B | #F4F5F7 | 14.6 | 4.5 | pass |
| text on white (ink on cards, inputs) | #1D222B | #FFFFFF | 16.0 | 4.5 | pass |
| body text on white (labels) | #3F4A5C | #FFFFFF | 9.0 | 4.5 | pass |
| muted text on page (small print, table headings) | #525F78 | #F4F5F7 | 5.9 | 4.5 | pass |
| muted text on white | #525F78 | #FFFFFF | 6.4 | 4.5 | pass |
| menu text on white shell (body) | #3F4A5C | #FFFFFF | 9.0 | 4.5 | pass |
| current menu pill (white on brand) | #FFFFFF | #0F4C35 | 10.0 | 4.5 | pass |
| primary button (white on brand) | #FFFFFF | #0F4C35 | 10.0 | 4.5 | pass |
| primary button hover (white on brand mid) | #FFFFFF | #2A7A5A | 5.2 | 4.5 | pass |
| link (brand on white) | #0F4C35 | #FFFFFF | 10.0 | 4.5 | pass |
| link (brand on page) | #0F4C35 | #F4F5F7 | 9.1 | 4.5 | pass |
| brand on selected tint | #0F4C35 | #E3F0EA | 8.5 | 4.5 | pass |
| input border on white (field) | #778399 | #FFFFFF | 3.8 | 3.0 | pass |
| card border on page (decorative) | #DDE2EC | #F4F5F7 | 1.2 | 1.0 | pass |
| success ink on success background (badge) | #08724E | #ECFAF5 | 5.5 | 4.5 | pass |
| success ink on white | #08724E | #FFFFFF | 6.0 | 4.5 | pass |
| success ink on page | #08724E | #F4F5F7 | 5.5 | 4.5 | pass |
| success line on success background (border, decorative) | #9FE5CD | #ECFAF5 | 1.3 | 1.0 | pass |
| warning ink on warning background (badge) | #8A4B00 | #FEF8ED | 6.4 | 4.5 | pass |
| warning ink on white | #8A4B00 | #FFFFFF | 6.8 | 4.5 | pass |
| warning ink on page | #8A4B00 | #F4F5F7 | 6.2 | 4.5 | pass |
| warning line on warning background (border, decorative) | #F5D48A | #FEF8ED | 1.4 | 1.0 | pass |
| danger ink on danger background (badge) | #BE3910 | #FEF0EC | 5.0 | 4.5 | pass |
| danger ink on white | #BE3910 | #FFFFFF | 5.6 | 4.5 | pass |
| danger ink on page | #BE3910 | #F4F5F7 | 5.1 | 4.5 | pass |
| danger line on danger background (border, decorative) | #F8B5A1 | #FEF0EC | 1.6 | 1.0 | pass |
| info ink on info background (badge) | #1A6175 | #EEF8FA | 6.5 | 4.5 | pass |
| info ink on white | #1A6175 | #FFFFFF | 7.0 | 4.5 | pass |
| info ink on page | #1A6175 | #F4F5F7 | 6.4 | 4.5 | pass |
| info line on info background (border, decorative) | #AADAE7 | #EEF8FA | 1.4 | 1.0 | pass |
| neutral ink on neutral background (badge) | #3F4A5C | #F0F3F9 | 8.1 | 4.5 | pass |
| neutral ink on white | #3F4A5C | #FFFFFF | 9.0 | 4.5 | pass |
| neutral ink on page | #3F4A5C | #F4F5F7 | 8.2 | 4.5 | pass |
| neutral line on neutral background (border, decorative) | #D5DBE6 | #F0F3F9 | 1.3 | 1.0 | pass |

## Checklist for a new screen

1. Colours, radius, spacing and fonts come from the tokens. No colour, size or font written by hand.
2. It is a `PageTemplate` and starts with a `PageHeader` card (see Page template).
3. Lists are a `DataTable` (it shows `LoadingSkeleton` while loading and `EmptyState` when empty); other content is in `ListCard` or `.ui-card`; a failure shows `LoadError`. A form is a `FormDrawer`, never open under a list.
4. Every control is a shared component (`AppButton`, `FormField`, `StatusBadge`, frappe-ui `Dialog`).
5. Money shows as `Rs 50,00,000` and dates as `24 Nov 2026, 11:44` (`formatMoney`, `formatWhen` in `src/format.js`).
6. Keep every `data-testid`.

## Screenshots, before and after

Company Admin of the demo company Pandya Realtors - BOM, 1280 by 800, 24 November 2026. Left of each pair is the old cream and dark green shell, right is this standard,
both on the same demo data. In `docs/ui-reference/ui-standard/`: `before-<page>.png` and `after-<page>.png` for Home, Leads, Deals, Commission, Call queue, WhatsApp, Site visits, Inventory, Sign in and Enquiry.
All four roles, every menu page and a phone pass are made by `cypress/integration/visual/walkthrough.cy.js` (`bench --site sellos_test.localhost run-ui-tests sellos --headless --spec cypress/integration/visual/walkthrough.cy.js`).
