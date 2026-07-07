# 0044 — `/acs:test` closed-loop ticketing semantics

**Status**: Accepted · **Date**: 2026-07-07

## Context

[ADR 0011](0011-sdlc-doc-sets-quality-and-operations.md) D6 says `/acs:test`
"opens an acs ticket per regression" and invokes the create-ticket flow "like
`/ship` orchestrates other skills," but settles neither the exact mechanism
nor the recurrence policy. Without a closed loop, a scheduled/cron run of
`/acs:test` either produces silent failures (an exit code nobody reads) or
floods the backlog with a duplicate ticket per run for the same underlying
regression. The model's value is turning a failing suite into an actionable,
deduplicated ticket — not either extreme.

## Decision

`/acs:test` triages a failing suite's captured output into a **regression
summary** and a **stable regression key** of the form
`<suite-name>:<normalized-failing-test-id>` (falling back to the coarse
`<suite>:__suite__` key when no individual failing-test id can be parsed out
of the failure output — a literal fixed marker, not a hash or fingerprint, so
a flaky/unparseable suite collapses onto one ticket per broken suite rather
than one per distinct failure blob). For each regression key, it reuses
`new-ticket.py` directly (unmodified) rather than the interactive
`/acs:create-ticket` skill, and applies a three-way recurrence policy:

1. **No existing ticket for this key → mint a new one** via `new-ticket.py
   --title ... --type task --description ...`, embedding an
   `acs-regression-key: <key>` marker for future lookup.
2. **An existing OPEN (open/in_progress/in_review) ticket for this key →
   comment-bump it** with fresh evidence (run id, timestamp, latest failure
   output) — never mint a duplicate, never silently skip.
3. **An existing CLOSED (done) ticket for this key recurs → mint a NEW
   ticket linked to the old one** — never silently reopen the closed ticket,
   since reopening it would hide that a shipped fix regressed.

No failure content (suite output, parsed test ids, triage summary text) is
ever interpolated into a shell command: `new-ticket.py` is invoked with
`--title`/`--type`/`--description` as argument values only; failure output
becomes ticket description content, never a command fragment (R1).

## Alternatives considered

- **Invoke the full `/acs:create-ticket` skill per regression** — *rejected*:
  its Step-2 user-confirmation gate (size/stakes/lane/needs_design) cannot be
  satisfied by a headless/cron run, directly conflicting with ADR 0011 D6's
  "runs unattended on a schedule"; also heavyweight — a near-full
  reflection-style inline run per failure, on every scheduled run.
- **Always mint a new ticket per failing run** — *rejected*: floods the
  backlog with duplicate tickets for the same underlying regression across
  repeated scheduled runs.
- **Always reopen the closed ticket on recurrence** — *rejected*: hides that
  a shipped fix regressed, since the ticket's history would read as "never
  actually fixed" rather than "fixed, then broke again."

## Consequences

- `/acs:test` remains deterministic and headless-safe — no interactive gate
  blocks a cron/scheduled run.
- The backlog stays both non-duplicated (comment-bump on open) and
  non-stale/honest (new-linked-ticket on recurrence after close).
- A `new-ticket.py`-minted regression ticket lands at conservative defaults
  (`size=standard`, `stakes=normal`) and must be triaged/reclassified by a
  human later — an accepted, explicitly-stated trade-off for an auto-filed
  regression, not a silent gap.
- A suite known to be flaky is a suite-authoring concern this closed loop
  does not special-case; the `__suite__` fallback bounds its ticket noise to
  one ticket per broken suite rather than amplifying it.
