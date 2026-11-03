# SellOS Kickoff

Use this with Tasks.md. Tasks.md is the backlog, and this file is how the first week starts.

## Your first three actions

1. **N16 Give Claude Code access.** Grant read access to the BuildOS repository, create the SellOS GitHub organisation with Claude Code access, and create a DigitalOcean token scoped to the staging and production projects only, with no billing or account level rights.
2. **N17 Name the pull request reviewer.** Decide who reviews, how fast, and who is the second reviewer from AMP Labs for security sensitive changes.
3. **N18 Decide the hosting.** Choose the DigitalOcean region, the droplet sizes for staging and production, and a monthly budget that includes backups.

Start these in parallel, because they need no engineering: N07 counsel review, N11 data source quotes, N12 the request to the Department of Registration and Stamps, N13 the party names advice, and N14 the Razorpay and Stripe accounts.

## First Claude Code session

Paste this once N16 is done. Run it in the BuildOS repository so Claude Code can read it, with the SellOS organisation available.

```
You are building SellOS, a multitenant real estate platform on Frappe 16.x,
hosted on DigitalOcean at one subdomain per company under
sellos.interactivesoftwares.com. Jayman reviews every pull request.

Read Tasks.md in full, especially "Rules for Claude Code". Then do story
P0.01 only: read this BuildOS repository and write a summary of its
structure, tooling, build process, frontend stack, testing approach and
styling, and list any change that Frappe 16 or SellOS needs.

Requirements for the summary:
1. Cover structure, tooling, build, frontend and tests.
2. Cite a BuildOS file or script for every point.
3. Save it as docs/buildos-conventions.md in a new branch and open a pull
   request titled P0.01.

Do not start any other story. Do not create repositories, servers or DNS
records yet. When the summary is done, stop and wait for Jayman's written
approval, which is the gate for P0.02 and P0.10.
```

## After P0.01 is approved

1. Claude Code does P0.02, then P0.03, P0.07 and P0.09 once the repositories exist.
2. AMP Labs and Claude Code do P0.04 once N18 is decided, then P0.05 and P0.06.
3. Claude Code builds P0.10, the web app shell, from the approved conventions.
4. Gate 0 is signed off when the conventions are approved, the web app signs in, and a test company site is created by script.

## Standing rules

* Calls placed from the 022 number are service or transactional only. The system refuses a promotional purpose.
* The Tata DLT and 140 series stories are parked in Tasks.md and are not worked on.
* No override on the consent check, no captcha solving, no secrets in repositories.
