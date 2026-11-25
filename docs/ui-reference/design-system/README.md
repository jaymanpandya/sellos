# Design system pass, before and after

Company Admin of the demo company, 25 November 2026. `before-*` is the production build running on the shared server (the SellOS UI
standard shell, before the layout pass and this pass); `after-*` is this branch. Each page at 1440 wide (`-1440`) and 390 wide (`-390`):
Home, Leads, a lead, Deals, Call queue, Inventory, Users, Telephony, Commission.
`check-before.txt` is the output of `scripts/check_design_system.py` the first time it ran: every page that failed, and why.
