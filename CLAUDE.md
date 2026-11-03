# SellOS

SellOS is a multitenant real estate platform for Indian agents, built on Frappe 16.x and hosted on DigitalOcean. Pandya Realtors is the first company on it. The AMP Labs builds it, Claude Code writes the code, and Jayman reviews every pull request.

## Where the work is defined

* Tasks.md is the backlog. Work one story at a time, in dependency order, and follow its "Rules for Claude Code".
* KICKOFF.md says how the first week starts.
* docs/legacy/SellOS_Build_Brief_v1.md is the earlier build brief. It is reference material only. Use it for domain field lists such as Project, Unit, Lead, Booking and Payment Schedule when the matching story needs them. Do not follow its phase order, its tenant field approach, or its instruction to create DocTypes in the Desk.

## Architecture decisions

1. One Frappe site and one database per company, at a subdomain of sellos.interactivesoftwares.com, plus a separate control site for the Platform Admin. A company never shares a database with another company.
2. Frappe 16.x without ERPNext. Pin the version.
3. DocTypes, hooks and patches live in the app repositories as code. Never create DocTypes through the Desk.
4. Customers never use the Frappe desk. Every customer feature is built in the SellOS web app, which follows the BuildOS frontend stack, structure and tooling once P0.01 is approved.
5. Every API method is whitelisted, declares its allowed roles, and is covered by the permission test matrix. A method with no declaration is denied.
6. Five roles: Platform Admin, Company Admin, Agent, Client and Channel Partner.
7. A consent check runs before every dial. It has no override for any role.
8. Calls placed from the 022 number are service or transactional only. A promotional call purpose is refused.
9. Secrets live in encrypted settings or environment variables, never in a repository.
10. Never build captcha solving or any bypass of an access control.

## Working rules

* Open one small pull request per story, titled with the story ID. Never push to the main branch.
* Write the tests named in the story's Test criteria with the code. Continuous integration must pass.
* Tick the story's checkbox and update its status in the pull request that completes it.
* Do not start a story whose dependencies are not ticked, and do not work on parked stories.
* Do the first story, P0.01, before anything else, and wait for Jayman's written approval of the BuildOS conventions summary.

## Stop and ask Jayman when

* A story needs a secret, account or access you do not have.
* An acceptance criterion is ambiguous.
* A change touches permissions, the consent check, billing or personal data.
* A dependency is blocked, or the plan and this file disagree.
