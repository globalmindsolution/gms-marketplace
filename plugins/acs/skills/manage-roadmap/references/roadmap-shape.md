# /acs:manage-roadmap — the roadmap document (ADR-0145)

`roadmap.md` sits beside the PRD hub (`<prd_dir>/roadmap.md`) and is written by
this skill alone. The author writes it, the floor (`roadmap_check.py`) and the
reviewer hold it to this page, and `acs.py roadmap status` rewrites its status.

```markdown
# Roadmap — <product>

## Milestones

### M1 Booking MVP — v0.1.0

- Status: planned
- Features: [Online booking](features/online-booking/prd.md), [SMS reminders](features/sms-reminders/prd.md)
- Epics: SHOP-12, SHOP-14
- Target: 2027-03-31

Why this milestone, and what a user can do once it ships — one paragraph.

### M2 Deposits — v0.2.0

- Status: planned
- Features: [Deposits](features/deposits/prd.md)
- Epics: none yet

...

## Release versions

| Version | Milestone | Epics | Status |
|---|---|---|---|
| v0.1.0 | M1 Booking MVP | SHOP-12, SHOP-14 | planned |
| v0.2.0 | M2 Deposits | — | planned |
```

## The rules

- **Milestones** are `###` headings under `## Milestones`, each ending `— v<major>.<minor>.<patch>`:
  the release version that is its home. Two milestones never share a version.
- **Features** link the feature PRDs the milestone delivers
  (`features/<slug>/prd.md`, relative to `roadmap.md`) — every one must exist.
  Every **Must-have** feature of the hub's index is in some milestone; a
  **Won't-have** feature is in none. A feature may span milestones (an MVP
  slice, then the rest): say which part in the paragraph.
- **Epics** name the epic tickets that deliver the milestone, or `none yet`.
  `/acs:create-ticket` mints them later; the roadmap never invents an id.
- **Target** is optional: a date the user gave, never one the author guessed.
- **Release versions** has one row per milestone — the same version, the same
  milestone name (the heading without its version), its epics, its status — so
  every committed milestone resolves to exactly one release version (0 orphan
  milestones) and no row names a milestone that is not there.
  `/acs:release` never reads this table to resolve tickets; it is for readers.
- **Status** is `planned`, `in progress` or `delivered`, and is **derived**,
  never written by hand: `acs.py roadmap status --write` reads the tickets each
  milestone tracks (its epics, and every ticket linking one of its features)
  from the tickets index and the default branch's history, and rewrites only the
  Status lines and cells. A new milestone starts `planned`.

## Versions

The roadmap carries the version front matter (ADR-0122, ADR-0130), set only by
the coordinator through `acs.py design`. A run that changes the plan — a
milestone added, moved, re-scoped or cut — is one version (`design bump`); a
status refresh alone is not a new version and moves no front matter, because
the status is a reading of the tickets, not a decision about the plan.
