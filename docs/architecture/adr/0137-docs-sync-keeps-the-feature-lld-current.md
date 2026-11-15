# 0137 — `/acs:docs-sync` keeps the feature's LLD current, and moves a matching design to `implemented`

**Status**: Accepted · **Date**: 2026-10-05

**Amends**: [0122](0122-design-versions-and-gap-detection.md) (the lifecycle's
`approved → implemented` step, which §1 gave to `/acs:docs-sync`, now has an
owner that runs it), [0126](0126-lld-data-design-and-flows.md) and
[0134](0134-api-contract-is-a-design-document.md) (both recorded that
`/acs:docs-sync` did not yet keep `lld/<feature>/` current after
implementation — P7; it now does).

## Context

`/acs:docs-sync` reconciles a run's documentation with its changeset. It runs
one `docs-sync-doc-updater` per doc area — `requirements`, `architecture`,
`adr`, `general` — and judges the result with `docs-sync-drift-reviewer`
slices over six dimensions. That split predates the per-feature low-level
design:

- Since ADR-0126 and ADR-0134 a feature's detailed design lives in
  `<architecture_dir>/lld/<feature>/{api,data,flows,components}/`, written by
  `/acs:create-api-contract`, `/acs:create-data-design` and `/acs:create-flows`
  and versioned through `acs.py design` (ADR-0122). The `architecture` area
  owned every path under `architecture_dir`, but its charter still described
  the old flat `lld/flows/` folder, so a change that added a column, an
  endpoint field or a state left the feature's documents describing the code
  as it was before the ticket.
- ADR-0122 gave `/acs:docs-sync` the move from `approved` to `implemented`,
  and `acs_lib.design_docs` records it as docs-sync's. docs-sync never ran it.
  An approved design stayed `approved` after its code shipped, and
  `/acs:audit-design` could not tell a built design from one still waiting:
  the only way to record the step was a `design status --set implemented` by
  hand.
- An approved document is the team's sign-off. Rewriting it to match the code
  without asking would turn every implementation shortcut into the approved
  design; leaving it alone would let the code and the sign-off disagree in
  silence.

## Decision

1. **A fifth doc area, `lld`.** It owns
   `<architecture_dir>/lld/<feature>/{api,data,flows,components}/**` for the
   run's features — `context.requirements.features`, or the ticket's
   `features`. A run with no feature gives the area no work: it reports no
   delta, like any other area with none. The longest-prefix partition rule is
   unchanged, so `architecture` keeps the HLD and the legacy flat
   `lld/flows/` (still read and updated as before), and `lld` takes the
   per-feature folders. A run's record folder `lld/<feature>/<key>/`
   (`tech-design.md`, `api-contract.md`) is history and is never edited by
   docs-sync.
2. **A gap analyst per feature.** A new read-only agent,
   `docs-sync-gap-analyst` (kind `survey`, `tools: Read, Glob, Grep, Bash`),
   runs in iteration 1 in the same message as the doc-updaters, one instance
   per feature, capped by `settings.parallel.max_agents`. It compares the
   feature's living LLD documents with the implemented changeset and the code
   and classifies every element of every document — an operation, an entity,
   a flow, a component — as **matches**, **unimplemented**, **undocumented**
   or **drifted** (ADR-0122's three gap classes, plus the match that a status
   move needs), each with `file:line` evidence on both sides. It records each
   document's current `status` and `version` (`acs.py design check`) and a
   per-document verdict: **`implemented-candidate`** when every element
   matches and none is unimplemented, otherwise not. It writes
   `steps/docs-sync/iter-1/gaps-<feature>.md` through `acs.py write`
   (ADR-0136); the coordinator joins them with `acs.py notes merge` into
   `iter-1/gaps.md`, which the `lld` doc-updater and the drift reviewers read.
3. **The `lld` doc-updater never silently rewrites a contract.** By the
   document's status:
   - `proposed`, or no status: an undocumented or drifted element is written
     into the document to match the code and the document is bumped with
     `acs.py design bump`; an unimplemented element is left as it is — it is
     planned, and the document stays `proposed`.
   - `approved` or `implemented`: any drifted or undocumented element is a
     question in docs-sync's one grouped ask — *the code differs from the
     approved `<doc>` (`<element>`, evidence)*: **(a)** update the document to
     match the code — it is bumped, which sets it back to `proposed` for
     re-approval — or **(b)** keep the document: the code is wrong, and that
     is a blocking finding for `/acs:code`. With no user to ask (headless, or
     under `/acs:ship` without an answer) the question is recorded the way the
     skill already records an unanswerable one — a blocking finding and
     `needs_input` — and docs-sync never picks an option itself.
   - `deprecated`: never touched.
4. **The coordinator moves `approved → implemented`.** After the drift review
   passes, every document whose gap notes say `implemented-candidate` is moved
   in one call:
   `acs.py design status --set implemented --by acs --reason "<run-id>: the code matches" <doc>...`
   — ADR-0130's all-or-nothing verb, so one illegal transition leaves every
   document as it was. A document with any element still unimplemented stays
   `approved`: a design delivered across several tickets reaches
   `implemented` with the ticket that finishes it. The result records the
   moved paths in `states.implemented` (a list) and every document bumped or
   edited in `states.files`, which `/acs:create-pr` commits with docs-sync's
   other updates.
5. **The drift reviewer gains a seventh dimension, `lld-currency`.** It
   checks that the run's feature LLD documents reflect the code per the gap
   notes, that every edited document was bumped, that no `approved` or
   `implemented` document changed without a recorded answer, and that every
   move to `implemented` is backed by an `implemented-candidate` verdict whose
   evidence holds. It joins the `placement` slice (4 mechanics, 5
   requirements-routing, 7 lld-currency), so the reviewer still runs as three
   slices. Dimension 5, `requirements-routing`, keeps the living requirements
   and drops its wording about the flat `lld/flows/` folder.

## Consequences

- **The lifecycle closes.** A design goes `proposed` (Design skills) →
  `approved` (`/acs:set-doc-status`) → `implemented` (`/acs:docs-sync`, once
  the code matches), and `/acs:audit-design` reads an unimplemented element in
  an `implemented` document as the regression ADR-0122 meant it to be. A
  `design status --set implemented` by hand is still legal, but no longer the
  only way.
- **An approved design is never rewritten without the team.** Drift against
  an approved document is either re-opened for approval or sent back to the
  code as a blocking finding; in a headless run it stops the run for input
  rather than choosing.
- **Re-designing to follow the code is no longer needed** for a change that
  only moved a schema, an interface or a flow: docs-sync brings a `proposed`
  document along and asks about an approved one. Re-running a Design skill is
  still how a design changes ahead of the code.
- 35 agent files, all reachable; the role `gap-analyst` already existed, so
  the only new setting is `models.docs-sync.gap-analyst` in the scaffold. The
  write → judge loops stay eleven.
- docs-sync costs one more parallel survey per feature in iteration 1 and no
  extra wall-clock: the gap analysts run in the same message as the
  doc-updaters. A run with no feature spawns none.
- Two behaviour cases pin the new behaviour:
  `docs-sync-flips-approved-to-implemented` (an approved `lld/<f>/data/`
  document whose code now fully matches ends `implemented`, with
  `status_by`, `status_at` and `status_reason`) and
  `docs-sync-asks-on-approved-drift` (the code adds a field the approved api
  document lacks, and the grouped ask offers update-and-reapprove or keep).
- Not breaking: no setting, state shape or command is removed, and a run
  whose ticket names no feature behaves as before.
