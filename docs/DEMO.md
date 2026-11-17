# The SellOS demo environment (SOS-DEMO-1)

A control site and two company sites with realistic data, to look at in a browser. **No gate touches them**:
the gate's site check, clean check and leak check ignore every `sellos_tenant_demo<id>.localhost` site, the
baseline restore refuses to wipe them, and `tenant_sites.drop` refuses to drop them (so a test, the
provisioning worker's retry and `scripts/tenant-site.sh drop` cannot). Only `scripts/demo.sh reset` drops them.

## Commands

```
scripts/demo.sh seed     # make what is missing (sites, users, data), start the server. Safe to repeat
scripts/demo.sh reset    # drop the demo sites and databases, then seed from nothing (about 3 minutes)
scripts/demo.sh status   # which sites exist, whether the server answers for each
scripts/demo.sh start    # install and start the LaunchAgent com.sellos.demo
scripts/demo.sh stop     # stop the server. The sites and their data stay
```

## How it is built

* **Sites** are `sellos_tenant_democontrol.localhost`, `sellos_tenant_demoalpha.localhost` and
  `sellos_tenant_demobeta.localhost`. The control site holds a Tenant and a Provisioning Job for each company,
  and its worker (`sellos.provisioning.worker`) makes the company site with the MariaDB provisioner account,
  installs SellOS and sets up the Company Admin: the same path a real tenant takes (needs the provisioner
  password, as for `tenant-site.sh`). The control site has outgoing email muted, so no login email is sent.
* **Server**: LaunchAgent `com.sellos.demo` runs `scripts/lib/demo_server.py` on **port 8006**, bound to
  127.0.0.1 only. It routes by the Host header and has no reloader, so it does not restart when the loop edits
  files. It answers 404 to any host that is not a demo site, so it can never serve BuildOS, Pamaa or the gate's
  site. Log: `~/iespl-baseline/sellos-demo.log`. `.localhost` names resolve to this machine in Chrome and
  Safari without any setup.
* **Ports**: BuildOS 8000, Pamaa 8002, SellOS gate server 8004, **SellOS demo 8006**.
* **Safety**: the seed refuses to run on any site that is not `sellos_tenant_demo<letters and digits>.localhost`,
  because it writes users with known passwords (`sellos.testing.demo.check_demo_site`). `scripts/demo.sh` has no
  argument that names another site.

## Sign ins

Every password is **`Demo@2026`**. They are published here on purpose and exist only on the demo sites.

### Control: http://sellos_tenant_democontrol.localhost:8006/sellos

| Role | Sign in |
|---|---|
| Platform Admin | `platform@demo.example.com` |

### Skyline Realty (Mumbai): http://sellos_tenant_demoalpha.localhost:8006/sellos

| Role | Sign in |
|---|---|
| Company Admin | `admin.skyline@demo.example.com` |
| Agent | `agent1.skyline@demo.example.com` |
| Agent | `agent2.skyline@demo.example.com` |
| Channel Partner | `partner.skyline@demo.example.com` |
| Client | `client.skyline@demo.example.com` |
| Platform Admin (support user only) | `platform@demo.example.com` |

### Greenfield Homes (Pune): http://sellos_tenant_demobeta.localhost:8006/sellos

| Role | Sign in |
|---|---|
| Company Admin | `admin.greenfield@demo.example.com` |
| Agent | `agent1.greenfield@demo.example.com` |
| Agent | `agent2.greenfield@demo.example.com` |
| Channel Partner | `partner.greenfield@demo.example.com` |
| Client | `client.greenfield@demo.example.com` |
| Platform Admin (support user only) | `platform@demo.example.com` |

## What is in each company

* 13 leads over 11 pipeline stages (New, Consent pending, Contacted, Qualified, Site visit booked, Site visit done,
  Negotiation, Booking, Closed won, Closed lost, Nurture): every stage has at least one lead.
* All four consent states, each with its warning: Consented (a live Consent Record), Opted out, Registered DND,
  and Unknown (no record, or only an expired one). Leads moved to Contacted without a live record show the
  warning in their stage log.
* Buyer requirements on every lead (budget, configuration, property type, localities, purpose, timeline, possession).
* Lead sources: the eight standard ones, a custom "Hoarding campaign" and a disabled "Old newspaper ad".
* Duplicates: two clients with the same phone number written two ways, and a lead whose client shares an email.
* Activities, a few open tasks (one overdue) and site visits.
* Phone numbers: only the Company Admin sees full numbers. The Agents, the Channel Partner and support see them
  masked (the last three digits). The Client role sees no lead.
* Support access: an **Active** grant (4 hours) and a **Revoked** one, both to the Platform Admin. A grant lasts
  4 hours at most, so run `scripts/demo.sh seed` again to renew the active one.
* The Channel Partner owns the leads from "Channel partner"; the Agents have the leads assigned to them.

## Not yet in the demo

* **Telephony settings** (SOS-P2-01): not merged when this was built. When it is, add its settings to
  `seed_company` in `sellos/testing/demo.py` and run `scripts/demo.sh seed`.

## When something looks wrong

`scripts/demo.sh status`, then `~/iespl-baseline/sellos-demo.log`. `scripts/demo.sh reset` rebuilds everything.
The demo uses the same SellOS code as the loop (`apps/sellos`), so a half merged change can show there too.
