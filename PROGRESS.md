# SellOS progress

Updated in every commit. Read CLAUDE.md, Tasks.md and this file at the start of each session.

## Done

* P0.01 0045f42 (conventions summary d1f9d25)
* P0.02 9c1331b
* P0.03 ce4a3d1, 19bae4e
* P0.07 33155b2, 7adddcc (CI green on 7adddcc)
* P0.09 this commit (gitleaks in pre-commit and Linters; a fake key was blocked locally)

## Working on

* P0.10

## Blocked

* None.

## Waiting on others

* N07, N09 to N18 and the other N stories (owners Jayman, Counsel, Accountant, AMP Labs).
* P0.04, P0.05, P0.06, P0.08, P0.12 wait on N18 (DigitalOcean decisions).

## Open questions (default chosen)

* P0.07 criterion 2 (a failing check blocks the merge): direct pushes to 1.0 cannot be blocked by CI. Default: left as is. It needs a GitHub branch rule set by Jayman, or a decision that it no longer applies.
* The CI concurrency group is keyed on the PR number, so a push to 1.0 cancels the previous push's CI run. Default: left as is.
