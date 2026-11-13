# SellOS web app

This is the SellOS web app, a Vue 3 single page app built with Vite and frappe-ui. Read the root `CLAUDE.md` first.

**The web app never uses the Frappe desk.** Every customer feature is built here, and no customer is sent to `/app`.

## Commands

Run from this folder, with Node 24:

* `npm install` installs the packages and updates `package-lock.json`. The gate and CI use `npm ci`.
* `npm run build` builds into `../sellos/public/frontend` and writes `../sellos/www/sellos.html`.
* `npm run dev` starts the Vite dev server. Run SellOS itself only with `cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004`, and never start, stop or touch the servers on port 8000 (BuildOS) or 8002 (Pamaa).

## Where things live

* Tokens (colours, fonts, spacing, radii): `src/theme/tokens.js`, wired into `tailwind.config.js`. Colours are CSS variables so each company can set its brand. The approved SellOS defaults (SOS-P1-06A) are brand #0f4c35, `--sos-brand-mid` #2a7a5a, accent #e8954a, Syne headings and DM Sans body text (served from the `@fontsource` packages). Do not hard code colours in components.
* Personas and roles: `src/personas.js`. It lists the roles, their areas and their navigation (the Sales Manager gets its persona in SOS-P1-18), with `personaFor`, `routeArea` and `inAreas`.
* Routes: `src/router.js`. Pages are lazy loaded from `src/pages/`, and each route declares its `meta.area`, which `personas.js` checks.
* Start up: `src/main.js`. API calls: `src/api.js`. Session: `src/session.js`.
* The app is served at `/sellos`. The route must match `frontendRoute` in `vite.config.js` and `website_route_rules` in `sellos/hooks.py`.

## Rules

* There are no unit tests in this folder. Browser behaviour is tested with Cypress specs in `cypress/integration/frontend/`, which select elements by `data-testid="sellos-..."`. Give every element a spec needs a test id.

* Plain JavaScript with ES modules, tabs for indentation.
* A new page needs a route with an area, and a persona that may see it.
* Stop and ask Jayman before changing which role can see an area.
