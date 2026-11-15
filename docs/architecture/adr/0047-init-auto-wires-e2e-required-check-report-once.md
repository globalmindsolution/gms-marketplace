# 0047 — `/acs:init` auto-wires the e2e required check, with a report-once fallback

**Status**: Accepted · **Date**: 2026-07-11

## Context

Once `acs-e2e.yml` exists (ADR 0045), it still needs to become a **required**
status check on the protected default branch before a red e2e actually
blocks a merge. `/acs:init` Steps 7c/7d already auto-wire the
conventions/tests checks this way (admin-detect + explicit consent). E2E-1
had to decide whether e2e follows that same auto-wire UX or is treated more
conservatively, given e2e is inherently slower/flakier than the other two
gates (`settings.schema.json` — `per_iteration` exists precisely because "e2e
is slow").

## Decision

New opt-in `/acs:init` Step 7f: copy the workflow + runner (like Step 7d),
reuse Step 7c's admin-detect. If `admin=true` **and** the user explicitly
consents, add the `E2E suite` context to the SAME unified
`required_status_checks.contexts` array `/acs:init` already manages
(alongside `Tests & coverage` / `Branch / PR / commit conventions`) — never a
second, competing `PUT`. The context is added only after the check has
reported a conclusion at least once (register-check-first, avoiding the
"unknown context" 422). Otherwise: print the exact `gh api … /protection`
command for an admin to run, **once** per `/acs:init` run, and continue —
never hard-fail init.

## Alternatives considered

- **Emit-and-document ONLY for e2e; never auto-mutate branch protection for
  the e2e check, even when admin** — *rejected*: strictly more conservative
  (an admin must take a deliberate, separate action), which some maintainers
  may prefer given e2e's slow/flaky-by-nature profile, but inconsistent with
  Step 7c/7d's established UX and strictly more manual work for a maintainer
  who does want the gate now, for no safety gain beyond what the report-once
  safeguard already buys. Recorded as the genuinely more conservative option
  the user considered and declined, not a strawman.
- **A dedicated standalone command to wire the gate** (e.g.
  `/acs:wire-e2e-gate`) — *rejected*: duplicates Step 7c/7d logic verbatim,
  adds new skill surface with no behavior the chosen approach cannot already
  provide inside `/acs:init`.

## Consequences

- Every teammate who is a repo admin gets the exact same UX as the
  conventions/tests gates — no e2e-specific ceremony to remember.
- Real operational blast radius if a repo enables e2e as required before the
  suite is actually stable — mitigated, not eliminated, by admin-detect +
  explicit consent, the report-once safeguard, and register-check-first
  ordering; `/acs:merge-pr`'s existing BEHIND carve-out + required-check
  polling gives a recovery path once the gate does report.
- A repo without `gh` admin access (or one that declines wiring) still gets
  the committed workflow file running and showing status on PRs — it simply
  cannot yet block a merge until an admin runs the printed command.
