# 0051 — Changelog aggregation is authoritative, archive-primary with an `[Unreleased]`-coverage cross-check

**Status**: Accepted · **Date**: 2026-07-12

## Context

The v0.4.1 cut shipped an empty `[Unreleased]` section by hand — the epic's
children shipped ADRs/arch-docs but never added `[Unreleased]` entries, so
the changelog for that release was authored entirely at cut time. This is
the load-bearing failure mode MAR-129's changelog-aggregation source must not
repeat: shipped work since the last tag must never ship silently empty
release notes.

## Decision

**Option D — hybrid: archive/git-log draft + `[Unreleased]` cross-check with
a coverage report.** `release_notes.py draft` authoritatively assembles the
`## [<version>] - <date>` section from the merged-ticket archive
(`archive/<id>/ticket.json` since `git describe --tags --abbrev=0` on
`main`), grouped by parent epic and carrying PR refs, with a `git log`/PR-title
defensive fallback when an archive entry's `create-pr-state.json` is absent.
The draft is cross-checked against the existing `[Unreleased]` block and a
coverage report is emitted (N merged / M covered / K missing). The archive
draft is **authoritative** — the skill writes the section, not merely
advisory flagging — and the human edits/approves the drafted section in the
release PR before merging.

## Alternatives considered

- **Option A — `[Unreleased]`-primary.** *Rejected outright*: this
  reproduces the exact v0.4.1 bug — `[Unreleased]` can be empty when
  children never add entries, silently shipping empty release notes.
- **Option C — `git log`-primary.** *Kept only as the defensive fallback*,
  not the primary path, because it loses epic grouping and
  Added/Fixed/Changed categorization that the archive's `parent` field
  provides for free.

## Consequences

- `draft_section` is never silently empty when ≥ 1 ticket merged since the
  last tag (AC-3) — directly defeats the v0.4.1 failure mode.
- Two sources (archive + `[Unreleased]`) must be reconciled; mitigated by the
  mandatory human edit/approve pass in the release PR review (ADR 0052).

## Amendment — MAR-306

**Date**: 2026-09-01 · **Status**: Accepted (append-only — Context/Decision/
Alternatives considered/Consequences above are unedited, following the same
append-only pattern as `docs/adr/0082-…md`'s "Amendment — MAR-6"/"Amendment —
MAR-1" sections, which themselves cite the
`0012-design-time-doc-consistency.md:75-152` precedent)

This ADR's Decision scoped the `git log` fallback narrowly — "a `git
log`/PR-title defensive fallback when an archive entry's
`create-pr-state.json` is absent" (above) — i.e. PR-*ref* resolution only.
MAR-306 widens the same defensive signal to *enumeration itself*: the new
`enumerate_git_log_tickets` recovers tickets that have no archive entry at
all, not just an archive entry missing its PR ref.

Archive-primary is preserved, not reversed: the archive is enumerated first
and an archive-derived id is never overridden (`exclude_ids=archive_ids`),
pinned by `test_archive_entry_takes_precedence_over_a_matching_commit_subject`;
with no ticket-ref subjects in history the fallback contributes no entries,
so the archive path's inputs/filters/ordering/output are unchanged apart
from the added `source` field, pinned by
`test_archive_only_enumeration_is_byte_identical_when_history_has_no_ticket_refs`
(which compares the enumeration with and without the fallback enabled, both
calls post-change — not a comparison against pre-MAR-306 behaviour).

Consequence: Option C's known costs (no epic grouping / no `docs_only`,
"Alternatives considered" above) now materialise on *fallback-sourced*
entries only, which is why each enumerated ticket is stamped `source:
archive|git-log`; the residual under-count this widening cannot recover is
an accepted limitation, with the ADR-0052 mandatory human-merge pass as the
backstop (`docs/operations/release-runbook.md`'s "Accepted limitations of
the git-log fallback" and "Human-review backstop" sections).
