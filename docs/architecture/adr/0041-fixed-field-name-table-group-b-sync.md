# 0041 — Fixed case-insensitive field-name table for Priority/Story Points/Parent, with type-driven value mapping and tracker-key-valued Parent field

**Status**: Accepted · **Date**: 2026-07-05

## Context

`ticket.json` already carries `priority`, `story_points`, and `parent`, but
none of the three was ever synced to the GitHub Project as a named field —
only Type/Status/Labels/Assignee/Milestone were. This ticket's design
(clarifications **C-5** and **C-6**) needed to settle the field-name mapping
convention, the value-mapping rule per GitHub field `dataType`, and the
representation of the parent/epic link on the board, given this repo's
Project defines none of the three fields under any name today.

## Decision

Priority, Story Points, and Parent sync via a fixed, built-in
case-insensitive name table, resolved by the same case-insensitive
name-match resolver `/acs:create-pr`'s existing Status fill already uses:

| acs field | Accepted board field names (case-insensitive) |
|---|---|
| `priority` | `Priority` |
| `story_points` | `Story Points`, `Points`, `Estimate` |
| `parent` | `Parent`, `Epic` |

Value mapping is driven by the resolved field's `dataType` (from
`gh project field-list`): **Priority** maps to a `SINGLE_SELECT` field by
case-insensitive option-name match against the ticket's `priority` value; no
match, or any other `dataType`, is an `info` finding, field left unset.
**Story Points** maps to a `NUMBER` field via `item-edit --number`, or to a
`SINGLE_SELECT` field (bucketed points) by matching the number's string form
against option names; no match is an `info` finding. **Parent** maps to a
`TEXT` field, set to the parent ticket's external tracker key (e.g. `#42`)
via `item-edit --text`; any other `dataType` is unresolvable and produces an
`info` finding. A board defining none of these names for a given field
produces the same `info`-finding fallback AC-6 already establishes for
Type/Status. `create-ticket` owns the creation-time fill on the issue's
Project item; `create-pr` owns the PR-side fill on the PR's Project item, at
PR-open time; there is no drift re-sync of a field changed on the board
after its write-moment.

## Alternatives considered

- **Configurable `tracker.github.field_map` settings key**, overriding the
  default table per acs field, defaulting to the fixed table when unset.
  Covers arbitrarily-named boards without a code change, and is additive
  (unset means the fixed-table behavior), but adds settings surface plus an
  `/acs:init` prompt and validation for a completion ticket whose live repo
  defines none of the three fields under any name — the map buys nothing
  here. Remains a non-foreclosed future extension since the fixed table
  becomes its default either way.
- **create-pr re-syncing the issue's fields on PR open** (in addition to the
  PR-item fill). Would catch create-time-to-PR-time edits to the ticket, but
  is unbounded-feeling — inviting "why not re-sync on every edit" — and the
  ticket's own DoD instructs an explicitly bounded scope; the PRD's tracker
  sync model is on-demand only, not periodic. No concrete need identified;
  rejected.

## Consequences

- A board using a differently-named field (e.g. "Effort" for points,
  "Severity" for priority) gets the `info`-finding skip instead of a sync
  hit — surfaced, never silent, but genuinely unsynced until the board is
  renamed or the table is extended in a future ticket.
- No new settings key is added; `plugins/acs/schemas/settings.schema.json`
  is unchanged.
- The **issue-level** parent link (`new-ticket.py --parent`, already
  shipped) is unaffected either way; this decision only concerns the
  Project-level field.
- On this repo (no Priority/Story Points/Parent field defined on the board),
  every one of the three fields produces an `info` finding and no `gh`
  `item-edit` write — the fallback path is the one exercised live.
