# The SellOS demo environment (SOS-DEMO-1)

A control site and two company sites with realistic data, to look at in a browser. **No gate touches them**:
the gate's site check, clean check and leak check ignore every `sellos_tenant_demo<id>.localhost` site, the
baseline restore refuses to wipe them, and `tenant_sites.drop` refuses to drop them (so a test, the
provisioning worker's retry and `scripts/tenant-site.sh drop` cannot). Only `scripts/demo.sh reset` drops them.

## Commands

```
scripts/demo.sh seed     # make what is missing (sites, users, data), start the server. Safe to repeat
scripts/demo.sh update   # migrate every demo site, restart the server, seed what is missing. Never drops or wipes
scripts/demo.sh reset    # drop the demo sites and databases, then seed from nothing (about 3 minutes)
scripts/demo.sh status   # which sites exist, whether the server answers for each
scripts/demo.sh start    # install and start the LaunchAgent com.sellos.demo
scripts/demo.sh stop     # stop the server. The sites and their data stay
```

`update` is the one to run after the loop merges new features: it makes new doctypes and fields exist (migrate),
restarts the demo server so it serves the new code, then seeds only what is missing (the seed looks up every
record first, so repeating it adds nothing). It never drops a site and never wipes data. Use `reset` only to
start from nothing.

## How it is built

* **Sites** are `sellos_tenant_democontrol.localhost`, `sellos_tenant_demobom.localhost` and
  `sellos_tenant_demoamd.localhost`. The control site holds a Tenant and a Provisioning Job for each company,
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

The control site holds one Tenant and one Provisioning Job for each company.

### Pandya Realtors - BOM (Mumbai): http://sellos_tenant_demobom.localhost:8006/sellos

| Role | Sign in |
|---|---|
| Company Admin | `admin.bom@demo.example.com` |
| Sales Manager | `sales.bom@demo.example.com` |
| Agent | `agent1.bom@demo.example.com` |
| Agent | `agent2.bom@demo.example.com` |
| Agent | `agent3.bom@demo.example.com` |
| Agent | `agent4.bom@demo.example.com` |
| Channel Partner | `partner.bom@demo.example.com` |
| Client | `client.bom@demo.example.com` |
| Platform Admin (support user only) | `platform@demo.example.com` |

### Pandya Realtors - AMD (Ahmedabad): http://sellos_tenant_demoamd.localhost:8006/sellos

| Role | Sign in |
|---|---|
| Company Admin | `admin.amd@demo.example.com` |
| Sales Manager | `sales.amd@demo.example.com` |
| Agent | `agent1.amd@demo.example.com` |
| Agent | `agent2.amd@demo.example.com` |
| Agent | `agent3.amd@demo.example.com` |
| Agent | `agent4.amd@demo.example.com` |
| Channel Partner | `partner.amd@demo.example.com` |
| Client | `client.amd@demo.example.com` |
| Platform Admin (support user only) | `platform@demo.example.com` |

## What is in each company

Each company is made by `sellos/testing/demo.py` from one builder per area (`demo_inventory.py`, `demo_crm.py`,
`demo_sales.py`, `demo_whatsapp.py`), through the production APIs, as the person who would do it. The names come from
`demo_names.py` and the volumes from `demo_ctx.py`. Everything is made up: no real developer, person, phone number
or RERA number. Phones are in the reserved fictional range, emails are on `example.com`, prices are in rupees with
Indian grouping. The seed is fixed (the same people every time) and looks every record up first, so repeating it
adds nothing. Nothing is named "Regression". At the end it prints a summary of what it created, renamed and removed
per doctype, and checks the minimums below on the site; a shortfall fails the seed.

At least, on each company:

* **Inventory**: 6 developers and 12 projects with fictional RERA numbers (Mumbai: `P518000` and five digits;
  Ahmedabad: the Gujarat RERA format), 60 units a project on average in towers or wings with floors, 1 to 4 BHK,
  carpet area, price per sq ft, possession dates, and available, held and sold units. 40 resale properties in 10
  localities (society, floor, age, asking price). Mumbai: Andheri West, Powai, Bandra East, Worli, Thane, Mulund,
  Chembur, Goregaon, Borivali, Navi Mumbai. Ahmedabad: SG Highway, Prahlad Nagar, Bopal, Shela, Gota, Satellite,
  Thaltej, Vastrapur, South Bopal, Science City.
* **Leads**: 180 across the 11 pipeline stages (at least 8 each), plain names (Mumbai: Gujarati, Marathi, Parsi,
  Punjabi, Jain, South Indian and NRI; Ahmedabad mainly Gujarati), the source as its own field, budget,
  configuration, timeline, project interest, notes, an assigned agent, a next follow up and created dates over the
  last 90 days. All four consent states, at least 15 each (live, expired and opted out records).
* **Activity**: 400 activity items, 120 call logs (through the fake provider) and a call queue, 50 site visits (the
  past 3 weeks and the next 2, every status, some tomorrow).
* **Sellers**: 25 sellers and 25 mandates in every status the Mandate allows.
* **Partners**: 12 channel partner firms with RERA registrations and rates, some approved and some pending, and the
  buyers they register.
* **Deals**: 30 deals with splits adding to 100 percent, and 24 commission payouts in Due, Approved, Paid and On hold.
* **WhatsApp**: 40 conversations (Hinglish and English; Gujarati for Ahmedabad) including a STOP, a handover to a
  human, one waiting for a reply and a template with no reply.
* **People**: a Company Admin, a Sales Manager with a sales team of the four agents, four agents, a Channel Partner
  (the contact of an approved firm) and a Client (a seller with enquiries on the property).
* **Settings**: Telephony is fake (`FAKEOK-DEMO-NOT-A-REAL-KEY`, no real key is stored, no call leaves the machine);
  the fake provider needs `allow_tests`, which the seed sets on the demo company sites only. A short do not call
  list, the consent wording with the company's name, and support grants (one Active, one Revoked; run
  `scripts/demo.sh seed` again to renew the Active one, which lasts 4 hours).
* **Phone numbers**: only the Company Admin sees full numbers; Agents, the Sales Manager, the Channel Partner and
  support see them masked.

## When something looks wrong

`scripts/demo.sh status`, then `~/iespl-baseline/sellos-demo.log`. `scripts/demo.sh reset` rebuilds everything.
The demo uses the same SellOS code as the loop (`apps/sellos`), so a half merged change can show there too.

**A failed seed step fails loudly.** Each part of a company's data (inventory, crm, inventory holds and sales, sales, whatsapp, the minimums) runs as its own step, so one broken step does not stop the rest. At the end `scripts/demo.sh seed` and `update` print `DEMO SEED FAILED:` with every failed site, step name and error (the full traceback of each is in the output above it) and exit 1. Repeating the seed retries only what is missing.

`update` adds the content above beside the records an earlier seed made, and it never wipes a site. The one thing it removes is the regression
seed's "Regression ..." records (clients and their leads, projects with their units, price lists and cost sheets, properties, listings,
developers): `remove_regression_records()` in `sellos/testing/demo.py` runs at the end of every company site's seed and on the control site,
behind `check_demo_site` (democontrol, demobom, demoamd only; `sellos_test` and every other site are refused). It prints what it removed
(`DEMO: removed from <site>: {...}`), prints `DEMO: kept on <site>: ...` for a Regression record that a real record still links to (that one is
left alone), finds nothing the second time, and leaves the four `regression_partner_*` users (a user is linked from the owner field of every
record). `scripts/demo.sh reset` rebuilds a site with only the realistic content.
