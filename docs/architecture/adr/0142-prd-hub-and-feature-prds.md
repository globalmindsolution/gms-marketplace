# 0142 — The PRD is a hub plus one PRD per feature, written by parallel authors

**Status**: Accepted · **Date**: 2026-10-09

**Amends**: [0130](0130-prd-versions-and-set-doc-status.md) (the version front
matter and `/acs:set-doc-status` reach every feature PRD, not only `prd.md` and
`roadmap.md`), [0140](0140-tickets-link-their-documents.md) (a ticket's PRD link
is the feature's own document, not a `#anchor` in `prd.md`) and
[0081](0081-create-prd-plan-conformance-corroboration-three-family-mechanism.md)
(an answer may anchor in a feature PRD; one more deterministic check joins the
floor).

## Context

`/acs:create-prd` produced one `prd.md` holding every feature, plus `roadmap.md`.
That works for a small product and stops working as the product grows: a single
file is one review thread, one merge conflict surface, and one document a single
author must hold in mind. The skill's three subagents (surveyor, author,
reviewer) fan the survey and the review out, but the write was a deliberate
single author, because `prd.md` and `roadmap.md` are one coupled deliverable —
and everything downstream (`doc_links`, `analyze-requirements`, tickets) located a
feature by guessing at a heading inside the one file.

Product-requirements practice for a growing product is a short, stable
product-level document and one requirements document per feature, joined by
stable ids and a traceability index.

## Decision

1. **The layout.** `prd.md` stays the *hub* with its eight sections; **Features
   (prioritized)** becomes the index — MoSCoW groups, one bullet per feature
   linking `features/<slug>/prd.md` and naming the goal ids it serves. Each
   feature has `<prd_dir>/features/<slug>/prd.md` — Summary, Goals served,
   Requirements (`R1`, `R2`, … per feature, never renumbered), Acceptance
   criteria, Dependencies, Out of scope. `<slug>` is the feature slug acs already
   uses (`lld/<slug>/`, a ticket's `features`), and the folder is the one the
   feature's living analysis already occupies. Priority lives only in the hub, so
   the two cannot drift. `roadmap.md` is unchanged.
2. **The authors.** The write fans out like the survey and the review: a `hub`
   author writes `prd.md` and `roadmap.md` first and alone (they remain one
   coupled pair, and it settles the feature set and the index), then one
   `feature-<slug>` author per feature runs in parallel, each owning one
   document. The surveyor records the feature set; a sliced survey's synthesis
   moves to the hub author. The reviewer's findings are routed to the author that
   owns the finding's file; a feature the run does not touch is not re-run and
   its version is not bumped. `acs:create-prd-author` is still one agent — the
   slice id names the role.
3. **The floor.** A new `prd_feature_check.py` holds the layout without a model:
   every Must/Should/Could bullet links a document, every link resolves, every
   document is linked, goal ids agree between the bullet and the feature's own
   **Goals served** and exist in the hub, the sections are present and ordered,
   requirement ids are present and unique. `prd_conformance_check.py` accepts a
   feature PRD as an answer anchor's target and reads each feature author's notes
   (`--feature-notes`), which win over the plan's placeholder line for the same
   ledger id — so no notes file has two writers and nothing is joined by hand.
4. **Versions and status.** Every document of the set carries the ADR-0122 block;
   `design list` lists a feature PRD in its feature's group with its analysis (the
   group label is now `feature <slug>`), so a feature can be approved as a unit.
5. **Links.** `doc_links` links a ticket's feature to `features/<slug>/prd.md`
   and the hub; the heading-anchor lookup is gone.
6. **No compatibility layer.** A repo with a single-file PRD is migrated by its
   next `/acs:create-prd` run (an amend), which splits the hub's features into
   documents; the old `#anchor` resolution is not kept. A Won't-have feature may
   have no document, and nothing deletes a feature PRD — retiring one is
   `/acs:set-doc-status deprecated`.

## Consequences

- A PRD change touches only the documents it changes: reviews, diffs and version
  bumps are per feature, and the write scales with the feature count rather than
  with the length of one file.
- The hub is a sequential step before the feature wave, and the reviewer's
  `substance` slice reads every document, so very large products pay for it in
  the review rather than the write; slicing the review by feature is open.
- The skill carries more moving parts (two author roles, one more checker). The
  checker is deterministic and the roles share one agent file, which keeps the
  surface small; `documents.md` is the one place the shapes are defined.
- Downstream skills that read the PRD for a feature (analysis, tickets, the
  architecture) have a document of their own to cite instead of a heading.
