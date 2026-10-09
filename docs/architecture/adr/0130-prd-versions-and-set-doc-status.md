# 0130 — PRD documents are versioned; `/acs:set-doc-status` approves and moves document status

**Status**: Accepted — amended by [0135](0135-create-tech-design.md) (§4: `design list` lists a run's `tech-design.md` from its per-run Design folder) and [0142](0142-prd-hub-and-feature-prds.md) (the block reaches every feature PRD) · **Date**: 2026-10-05

**Amends**: [0122](0122-design-versions-and-gap-detection.md) (the version front
matter reaches the PRD and the roadmap; a status move gains a skill, an approver
record — `status_by`, `status_at`, `status_reason` — and all-or-nothing writes
over several documents), [0128](0128-requirements-from-any-container.md) (the
documents in a run's Discovery and Design folders are listed by phase and feature
for a status move), and [0129](0129-discovery-design-development-regroup.md)
(Utility gains `/acs:set-doc-status`).

## Context

ADR-0122 gave every HLD and LLD document a version block — `status`, `version`,
`tickets`, `feature` — written only through `acs.py design`. Two gaps remained.

The PRD and the roadmap, the documents every later skill is verified against,
carried no block at all. `/acs:create-prd` amended them in place, so a reader
could not tell an approved PRD from a draft, nor which version a feature's
analysis or a design was written against. Feature analyses
(`<prd_dir>/features/<feature>/analysis.md`) were already versioned by
`/acs:analyze-requirements`, which made the PRD above them the odd one out.

Moving a status had no front door. ADR-0122 said the team's approval of the
design PR is the design's approval, but nothing recorded it: `design status
--set approved` was a raw CLI call the user had to know about, it recorded
neither who approved nor why, and over several documents it wrote the first
before refusing the second, leaving a half-approved feature behind.

## Decision

1. **The PRD documents are versioned.** `prd.md` and `roadmap.md` carry the same
   block as a design document (ADR-0122), set only through `acs.py design`.
   `/acs:create-prd`'s coordinator runs `design init --status proposed` on a new
   one and `design bump` on a changed one, then `design check` in its $0 floor.
   The author's byte-for-byte preservation rule and the reviewer's dimension on
   untouched content exempt the leading block: a changed document must show a
   bumped version instead. `/acs:code`'s implementer bumps `prd.md` or
   `roadmap.md` when it reconciles a factual claim in it. Feature analyses keep
   the versioning `/acs:analyze-requirements` already gives them.
2. **An approver record.** `design status --set S [--by NAME] [--reason TEXT]`
   writes, beside `status`, `status_by` (default `git config user.name
   <user.email>`), `status_at` (the time of the move) and `status_reason` (when
   given). The keys sit after ADR-0122's, so the block says who moved the
   document, when and why, not only where it stands. A status move never
   changes `version`; a `design bump` that re-opens an approved or implemented
   document drops the three keys, since they described the status it left, and
   a move given no reason drops an older `status_reason`.
3. **All or nothing.** A `design status` over several documents validates every
   target first — the file exists, its block is valid, the transition is legal
   (`acs_lib.design_docs.TRANSITIONS`) — and writes none when any is refused.
   Approving a feature's documents either moves all of them or leaves all of them
   as they were.
4. **`acs.py design list [--phase P] [--feature F]`** lists the versioned
   documents deterministically, grouped by phase and feature: Discovery — the
   PRD, the roadmap and each `<prd_dir>/features/<feature>/analysis.md`; Design —
   the HLD (`<architecture_dir>/hld/*.md`) and each feature's living LLD
   (`lld/<feature>/{api,data,flows,components}/`). A run's design-record folders
   (`lld/<feature>/<ticket-id or run-id>/`) are not listed. Each entry carries
   `path`, `status`, `version`, `problems` and `allowed` — the legal targets from
   its current status, empty for a document whose block has problems. The
   folders come from `acs_lib.doc_layout` (the phase folders of ADR-0128), the
   grouping from `acs_lib.doc_sets`, the one helper `/acs:create-pr`'s commit
   plan also uses.
5. **`/acs:set-doc-status`**, a new unhooked Utility skill, is the front door. It
   runs inline with no subagents and no run of its own: it reads `design list`,
   asks ONE grouped multi-select question that picks whole features, design areas
   or single documents (paged by phase when there are more than four options),
   then asks for the target status — only the moves `allowed` offers, `approved`
   first for proposed documents — and a reason, required for `deprecated` and
   optional otherwise. It confirms the list and runs one `design status --set`;
   it cannot edit a block itself (Edit and Write are disallowed to it).
   Arguments skip the asks (`/acs:set-doc-status approved wishlist`). It commits
   nothing (ADR-0127): it lists the changed files and points at `/acs:create-pr`.

## Consequences

- A reader sees where every Discovery and Design document stands and who moved
  it there, from the document itself; the docs PR that carries an approval is
  reviewable as a front-matter diff.
- 29 skills: `UNHOOKED_SKILLS` gains `set-doc-status` (19 hooked, 6 unhooked,
  `/acs:code`'s 4 legs); agent files and hooks are unchanged.
- ADR-0122's rule that a status is derived and validated, never asserted, now
  covers the approver too: `status_by` and `status_at` are written by the CLI,
  never typed into the block.
- A PRD written before this change has no block: `design check` reports it and
  the next `/acs:create-prd` run initialises it. This repo's own PRD is no
  exception.
- `/acs:docs-sync` still owns the move to `implemented` (ADR-0122); the skill
  offers it only where `allowed` does.
