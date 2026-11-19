# SellOS UI style guide (SOS-UI-1)

SellOS looks like PAMAA. Every value here is read from PAMAA's source
(`~/iespl-bench/apps/pamaa_erp/frontend`: `src/tokens.js`, `tailwind.config.js`, `src/index.css` and the files in
`src/components/`), not from notes. PAMAA is read only. The tokens are in `frontend/src/theme/ui-tokens.js` (JS) and
`frontend/src/theme/ui-tokens.css` (CSS variables, plus Inter). Neither is wired in yet: SOS-UI-2 does that.

Where the brief's starting values and PAMAA's source differ, the source is used:

| Item | Brief | PAMAA source (used) |
| --- | --- | --- |
| Indigo accent / button | about #3B3FE0 | `#323CE9`; the button is a gradient `#323CE9` to `#4650EC` |
| Page background, text | #F4F5F7, #1D222B | same |
| Sign in card | white, 14px, 1px border, two layer shadow | same: border `#DDE2EC`, shadow `lift` |
| Sign in input | 8px, about 34px, 14px | 8px radius, **32px** high, **16px** text (frappe-ui text input, size md) |
| In app field | not given | **10px** radius, **44px** high, 16px text (`.pamaa-control`) |
| Brand tile | square, company initial | square on sign in (44px, no radius, because frappe's radius scale has no `rounded-xl`); 10px rounded in the sidebar, 9px in the header |
| Top accent bar | indigo | 3px gradient from `#323CE9` to `#5962ED` (`brand-2`) along the card's top edge |

PAMAA's body text is 16px and its "extra small" is 14px (it raises Tailwind's scale). Page background is `#F4F5F7` with a
faint blue, teal and green radial wash in the corners.

Screenshot: `docs/ui-reference/pamaa-sign-in.png` (PAMAA's sign in page, captured from the running app). The other
patterns could not be photographed: that needs a PAMAA login, and none was available to me. Each section below names the
PAMAA file to open instead. Add the screenshots when someone with a PAMAA login can capture them.

## Tokens

* **Font:** Inter 400, 500, 600, 700 (`ui-tokens.css` loads it from Google Fonts, as PAMAA does). Fallbacks: InterVar, system-ui, Segoe UI, sans-serif.
* **Text colours:** ink `#1D222B` (text), body `#3F4A5C` (labels, secondary), muted `#525F78` (small print, table headings, crumbs).
* **Borders:** line `#DDE2EC` (cards, header), line-soft `#EBEEF4` (table row lines), field `#8A96AD` (input borders).
* **Surfaces:** page `#F4F5F7`, white cards, faint `#F8F9FB` (quiet boxes), subtle `#EEF1F6` (locked areas).
* **Brand:** `#323CE9`; second `#5962ED`; soft tint `#F0F1FE` (hover, selected); link `#323CE9`; tag background `#E4E7FD`.
* **Status tones** (ink / background / line): success `#08724E / #ECFAF5 / #9FE5CD`; warn `#8A4B00 / #FEF8ED / #F5D48A`;
  danger `#BE3910 / #FEF0EC / #F8B5A1`; neutral `#3F4A5C / #F0F3F9 / #D5DBE6`; info `#1E248B / #F3F4FF / #ABB1F6`.
  Required mark and error text: `#B42318`.
* **Type scale:** title 24px/1.25, 600; heading 13px, 600, uppercase, 0.06em tracking; small 14px; body 16px; stat number 24px, 600, tabular figures. Line height 1.5.
* **Spacing:** Tailwind's 4px scale. Page padding 16px (24px from 640px wide), top 20px. Card padding 16px (20px from 640px; 32px on sign in). Form grid gaps 20px across, 16px down. Controls at least 44px tall and wide.
* **Radius:** card 14px, control 10px, sign in input 8px, pill 9999px.
* **Shadows:** card `0 1px 2px rgba(17,24,39,.04), 0 6px 20px -8px rgba(17,24,39,.10)`; lift `0 2px 4px rgba(17,24,39,.05), 0 14px 32px -12px rgba(17,24,39,.18)` (sign in card, menus, toasts); button `0 1px 2px rgba(30,36,139,.25), 0 4px 12px -4px rgba(50,60,233,.4)`.
* **Motion:** 120, 180, 250 ms, ease `cubic-bezier(0.16, 1, 0.3, 1)`. All of it is switched off under `prefers-reduced-motion`.
* **Icons:** Lucide.

## Patterns

**Sign in** (`pages/app/Login.vue`, `components/PageCard.vue`, `BrandMark.vue`). Centred card, `max-w-md` (448px), 12vh from the top, white, 14px radius, 1px line border, `lift` shadow, 32px padding, a 3px gradient bar on its top edge. Brand tile 44px, brand gradient, white initial 18px/600, `shadow button`, then the name 18px/600 with 0.08em tracking and the company line 16px muted. Title 24px/600, text muted. Labels 16px body colour with a red `*` when required. Full width solid button.

**Shell** (`components/AppShell.vue`). Computer: fixed sidebar 240px on the left with a right border, header on top, main with 16/24px side padding. Phone and tablet: no sidebar; a bottom bar (max five places plus More, items 56px tall, active item in the brand colour with a soft round icon background) and a More drawer that rises from the bottom.

**Sidebar** (`AppSidebar.vue`). White at 80% with a backdrop blur. Logo row 61px tall: 36px tile (10px radius, brand gradient, white initial 14px/600, `shadow button`) and the name 16px/600, 0.08em tracking. Sections are collapsible: a 24px round soft chip with an icon, the section name in the heading style (13px uppercase, muted), a chevron. Items are 44px tall, 10px radius, 16px body colour, hover on the page colour. The open item is white, semibold, on a brand gradient highlight that slides between items.

**Header** (`AppTopBar.vue`). Sticky, at least 61px, white at 85% with blur, 1px bottom line. Left: breadcrumb 16px muted with the current page in bold ink. Right: search, help, status chips, then the user button (36px round soft avatar with initials, name from 768px) which opens a menu: 256px, 14px radius, `lift` shadow, 44px rows with a muted icon.

**Page header** (`ListHeader.vue`). Title 24px/600, one line of body-colour text under it (16px, max 48rem), actions on the right. A 44px round area chip with an icon sits to the left from 640px. The main action is a solid button.

**Cards** (`.pamaa-card`). White, 14px radius, 1px line border, `card` shadow. A card heading is the uppercase muted style. Stat cards add the 3px top bar, a 32px chip, a 24px number and a 14px muted note, and lift 2px on hover (mouse only). Never put a gradient behind a table or a long form.

**Tables** (`DataTable.vue`). Inside a card. Header cells 14px, 600, uppercase, 0.06em, muted, with a 1px line under them. Body cells 16px, padding 8px by 10px, a 1px line-soft under each row, one line unless the text is over 40 characters. A clickable row gets the brand soft tint on hover and focus. The table scrolls inside its card. On a phone each row becomes a card: a two column list of small muted label over value. While loading, show shimmer rows, never the bare word.

**Forms** (`FormSection.vue`, `AccessField.vue`). A section is a card with an uppercase heading, an optional 16px body line, and a one column grid that goes to two or three columns from 768px. Label above the field, 16px body colour, red `*` when required. Field: white, 10px radius, 1px `#8A96AD` border, 16px text, 44px tall, 12px side padding. Focus: brand border and a 2px brand ring at 40%. A wrong field turns its border red. Hints and errors are 14px under the field (muted, or `#B42318` as an alert). Checkboxes are 20px.

**Buttons** (`.pamaa-button`, `.pamaa-button-solid`). 44px tall, 10px radius, 16px/500, 18px side padding, 8px gap for an icon. Outlined: white, brand text, brand border at 35%, soft tint on hover. Solid (one per screen, the main action): brand gradient, white text, transparent border, `button` shadow, brighter on hover. Disabled: 50% opacity. They squeeze to 94% when pressed. Focus ring as for fields.

**Status badges** (`StatusPill.vue`). Pill, 1px line in the tone's line colour, tone background, tone ink, 14px/500, `2px 10px` padding, a 14px icon then the word. Always the word and the icon, never colour alone. Tones: success (on track, done), warn (at risk), danger (late), info (in progress), neutral (not started).

**Empty state** (`EmptyState.vue`). A 14px radius box with a dashed border (brand at 25%), the `grad-empty` background, centred, 32px vertical padding: a 44px round chip with an icon, a semibold title, a 16px muted line (max 28rem), then an optional action.

**Error and load error** (`LoadError.vue`, `ErrorPage.vue`). A load error is a warn tone box: 14px radius, warn line and background, 16px warn ink text, a warn icon, and a "Try again" link under the message. A whole page error uses the sign in card with a solid "Try again" button. Errors say what happened in plain words and offer the next step.

**Toasts** (`ToastHost.vue`). Bottom centre on a phone, bottom right from 640px; white, 14px radius, 1px border in the tone's line colour, `lift` shadow, 44px tall, max 384px, the tone icon (a drawn check for success), ink text, and a 44px close button. They slide up in 220ms and leave to the side.

## How a new screen must look (checklist)

1. Colours, radii, shadows and fonts come from `ui-tokens.js` / `ui-tokens.css`. No colour, size or font written by hand.
2. Page background is the page colour, text is ink, font is Inter. Body text is 16px; small print is 14px muted.
3. The screen sits in the shell: sidebar on a computer, bottom bar on a phone, header with breadcrumb. It starts with a page header: title 24px/600, one line of text, the main action on the right.
4. Content is in white cards: 14px radius, 1px line border, `card` shadow, 16 to 20px padding, an uppercase heading.
5. Lists are tables in a card with the PAMAA header style, line-soft row lines, and card rows on a phone. Loading shows shimmer rows.
6. Forms: label above, 44px fields with 10px radius, red `*` for required, hints and errors in 14px under the field, one column on a phone.
7. One solid brand button per screen (the main action); everything else outlined. Every control is at least 44px.
8. Status is a pill with a word, an icon and a tone from the five tones. Never colour alone.
9. A list with no rows shows the empty state with a next step. A failed load shows the load error with "Try again". Saved or failed actions show a toast.
10. Keep every existing `data-testid`. No gradients behind tables or forms. Motion is short and off under reduced motion.
