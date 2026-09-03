# 0088 — gh is acs's only GitHub transport; failures are classified, not routed around

**Status**: Accepted · **Date**: 2026-09-03

## Context

acs's three apply-work skills (`create-ticket`, `create-pr`, `merge-pr`) shell
out to `gh` in prose at every write and every gate-input read. In a
session-restricted Claude Code container every repo-scoped `gh` call returns
HTTP 403 ("GitHub access is not enabled for this session…") while
`gh auth status` and `gh api user` both still exit 0 — presence, and even
account-level auth, are not capability (measured in the parent epic's design,
`MAR-401/design.md`, Problem A). `create-pr/SKILL.md` had already grown a
`### GitHub MCP fallback (no gh CLI)` section (MAR-307) that re-issued
selected operations as `mcp__github__*` tool calls when `gh` was blocked, and
merge-pr's post-merge tracker sync (`### Step 2 — Cleanup`) had no failure
rule of any kind — a tracker-close failure after a merge landed could still
abort the run.

Three options were weighed:

- **Status quo plus documentation.** Zero blast radius, but leaves Step 2
  unguarded and gives nothing for a test to cover.
- **A sanctioned second transport, GitHub MCP.** Preserves autonomy in the
  exact session class that motivated this decision — the MCP tools worked in
  that session while `gh` did not — but adds a second authenticated surface
  outside acs's "CLIs own auth, no secrets in settings" story, an external
  tool-name contract acs cannot version-pin, and a mapping that is
  incomplete by construction (Projects v2 has no discovered MCP equivalent),
  so the degradation rule this option was meant to replace still has to
  exist anyway.
- **gh-only, per-operation criticality plus actionable diagnostics
  (chosen).** `gh` stays the single GitHub transport everywhere. Every
  in-scope call is classified by consequence — critical when the run cannot
  correctly proceed without it, non-critical when the run can proceed with a
  recorded degradation — and each class gets an explicit, documented failure
  behaviour.

The user's explicit direction (clarification C-6 of epic MAR-401): *"gh CLI
only in both environments. No MCP-fallback mechanism in acs."*

## Decision

**`gh` is acs's only GitHub transport, in every environment.** No skill or
agent offers or implies a second GitHub transport. Every in-scope `gh`
operation across `create-ticket/SKILL.md`, `create-pr/SKILL.md`, and
`merge-pr/SKILL.md` is classified into exactly one of four disposition
classes, and a failed call is never silently routed around: **critical**
(gh's stderr verbatim plus one canonical hint, then the run stops),
**critical (per ticket), soft (per batch)** (an error-severity finding
naming that ticket, `replayable: false`, but the batch continues to the
next ticket), **non-critical** (one `info`-severity finding, the run
continues), or **loud-but-non-reverting** (one `error`-severity finding, the
run continues, and an already-completed action is never reverted or
re-attempted):

- **Critical** — the writes the run cannot proceed without (`gh pr create` /
  `gh pr edit`, `gh issue view` on import, `gh pr merge` at both the
  ticketed `### Step 1 — Merge` site and the exempt non-ticket-PR-mode
  site) **and** the reads whose failure leaves a decision
  or a readiness gate unevaluable (`gh pr list`, `gh repo view --json
  defaultBranchRef`, merge-pr's resume-reconcile `gh pr view`, its Step 0
  readiness `gh pr view` / `gh pr checks --required`, and the BEHIND
  carve-out's `gh pr update-branch` poll). An unevaluable gate is never
  treated as passed, so widening "critical" to these gate-input reads is a
  deliberate behaviour change, not a restatement: a failed `merge-pr`
  readiness read now **stops** a run that could previously have degraded. On
  a non-zero exit, a critical operation surfaces `gh`'s stderr **verbatim**
  plus one canonical, acs-authored hint sentence (`acs_lib.GH_ACCESS_HINT`,
  selected by the pure `acs_lib.gh_failure_hint(stderr_text)`), then the run
  **stops** — no fallback to any other transport.
- **Critical per ticket, soft per batch** — `create-ticket/SKILL.md`'s Step
  5 `gh issue create` tracker-sync call is a hybrid disposition, distinct
  from plain critical: a failed create for one ticket is an
  **error**-severity finding naming that ticket's id, gh's verbatim
  stderr, and the canonical hint, `replayable: false`, but the batch is
  never aborted — the loop continues to the next ticket, and only that one
  ticket's `external` stays null.
- **Non-critical** — metadata operations (labels, assignee, milestone,
  Projects v2 `item-add`/`field-list`/`item-edit`, CODEOWNERS reviewer
  request, the PR back-reference issue comment, and the `gh run list` CI
  diagnostic read) degrade to one `info`-severity finding (command +
  verbatim error + the same hint + a replayable `gh` command block) and the
  run **continues**.

**merge-pr's post-merge tracker sync is loud-but-non-reverting, a new rule
where none existed today.** By the time `### Step 2 — Cleanup` runs,
`### Step 1 — Merge` has already landed the merge. A Step-2 failure is never
grounds to revert or re-attempt the merge: it is reported as an
error-severity finding naming the outstanding sync, with a replayable block,
and the run still finishes `merged: true`.

**The canonical diagnostic lives once, in `acs_lib.py`, quoted by all three
skills.** `GH_ACCESS_DENIED_MARKER`, `GH_ACCESS_HINT`, `GH_GENERIC_HINT`, and
the pure `gh_failure_hint(stderr_text)` predicate are pure, stdlib, no I/O,
no network, no new import — a single source of truth for the hint sentence,
drift-tested against all three SKILL.md bodies and the three apply-work
executor agents, rather than three copies that could diverge. The
`GH_ACCESS_DENIED_MARKER` substring is proxy-owned and unversioned, so it
selects **wording only**: control flow is always the exit code plus the
operation's class, so a changed 403 body degrades the hint and can never
misroute a run.

**The `### GitHub MCP fallback (no gh CLI)` section is removed, not left to
rot.** `create-pr/SKILL.md`'s MAR-307 section is replaced by the gh-only
classification rule above, and the `actions_list`/`actions_get` "when `gh` is
unavailable" aside inside the surviving CI-troubleshooting section is deleted
with it. This ADR records that removal explicitly so it reads as a
considered reversal, not an accident: the MCP path worked, by hand, in the
session that motivated this decision — it is removed on an
ownership/contract-surface judgement (see Context), not because it failed.

This decision is scoped to the gh-transport and call-criticality question
only. The sibling decision on the ticket-id allocation fail-closed
reconciliation gate, split from the same parent epic (MAR-401), shipped
separately as ADR-0087.

## Consequences

**Positive**: no second authenticated surface to audit, no external
tool-name contract to version-pin, no per-operation agent-tool-call cost or
context growth on an already-degraded path. merge-pr's previously-unguarded
post-merge sync now has an explicit rule, closing the one place a partial
failure could abort a run after a merge had already landed. Every degraded
operation is now diagnosable: gh's own error plus one actionable,
acs-authored hint, plus a replayable command, instead of a bare stderr line
in a file no one reads at the moment of failure.

**Accepted cost**: this does **not** restore autonomy. In a session where
`gh` cannot reach the repo, `/acs:create-pr` and `/acs:merge-pr` still stop —
that was true before this decision and remains true after it. The value here
is diagnostic quality and a correct partial-failure policy, not new
capability, and it is stated plainly rather than dressed up.

**Behaviour change, not merely documentation**: gate-input reads that were
previously read as report-only now stop the run on failure, because an
unevaluable gate is never a passed gate. This widens no credential surface —
same `gh` binary, same auth, same repo scope — but it does change what a
degraded session experiences on a `merge-pr` readiness read.

**Known limitation, accepted**: prose is the only enforcement inside the
three apply-work skills — they run inline with no verifier leg
(`c4-component.md:80-84`), so nothing at runtime catches a missed
classification; only the anti-drift tests that import `acs_lib.GH_ACCESS_HINT`
rather than hardcoding it catch a copy that has drifted from the canon.
