# 0134 — The API contract is a Design document: `/acs:create-api-contract` leaves the pipeline and writes documents only

**Status**: Accepted — amended by [0137](0137-docs-sync-keeps-the-feature-lld-current.md) (`/acs:docs-sync` keeps `lld/<feature>/api/` current after implementation — P7 has landed) · **Date**: 2026-10-05

**Amends**: [0118](0118-discovery-design-development-phases.md) (§4's move of
`create-api-contract` out of `ship.yaml` into Design lands here),
[0128](0128-requirements-from-any-container.md) (the Design folder's
`api-contract.md` is now a per-run record beside the living
`lld/<feature>/api/` files it links, and the skill takes any container without a
plan), [0129](0129-discovery-design-development-regroup.md) (`/acs:create-api-contract`
is listed under Design and no longer runs as a `ship.yaml` step) and
[0133](0133-analysis-is-a-folder-by-bounded-context.md) (the analysis
`README.md` no longer carries `api_surface`).

## Context

`/acs:create-api-contract` was the third step of `workflows/ship.yaml`, between
`/acs:create-impl-plan` and `/acs:create-test-docs`. It read the approved plan,
traced every item to an acceptance criterion **and** to the plan item that
introduced it, and wrote two kinds of output: the run's `api-contract.md`, and —
when the repo kept them — the machine-readable contract files themselves
(OpenAPI, JSON Schema, proto, AsyncAPI), found through a `contracts_mode` /
`<contracts_dir>` detection and written in per-file-group slices. Whether it
ran at all hung on `/acs:analyze-requirements`' `api_surface` verdict: the
plan carried it into `owes.api_contract`, and a plan that owed nothing let the
pre-hook settle the step as `no_surface_owed`.

That put an interface's design after its implementation plan. The plan was
written without the contract it was going to implement, so the planner guessed
the shapes the contract then fixed, and a contract that disagreed with the plan
could only send the run back. It also made the step the one Design-shaped
document that lived only per run: `/acs:create-data-design` and
`/acs:create-flows` keep a feature's living `data/` and `flows/` documents,
versioned and checked for design gaps (ADR-0122, ADR-0126), while the
feature's `lld/<feature>/api/` folder — an `api-contract` LLD type in the
catalog since ADR-0120 — had no writer. And it was the one documenting skill
that edited code-adjacent files: a machine-readable contract is an
implementation artifact, generated and validated with the code that serves it,
yet it was written by a skill that never ran the code.

ADR-0118 §4 already named the move: `create-api-contract` leaves `ship.yaml`
for Design. ADR-0129 listed it under Design while it still ran as a step.

## Decision

1. **`/acs:create-api-contract` is a Design skill**, beside
   `/acs:create-data-design` and `/acs:create-flows`, in `PLANNING_SKILLS`
   rather than the workflow skills. `workflows/ship.yaml` drops the step and
   keeps eight entries; `/acs:ship` never runs it. Its gate is the one the other
   Design skills pass: the subject resolves from any container (ADR-0128) —
   a ticket, a feature slug, documents or a prompt — and **epics are allowed**,
   because Design runs on epics.
2. **No plan, no plan items.** It reads the run's requirements
   (`context.requirements`), the feature's analysis (README first, then the
   contexts it needs), the HLD's `integration-map.md` and the API conventions in
   `cross-cutting.md`, the feature's existing `lld/<feature>/api/` and
   `lld/<feature>/data/` documents, and the interfaces in the code. Every item
   traces to an acceptance criterion; nothing traces to a plan item.
3. **It owns the `api-contract` LLD type** (`design.lld_types`). With the type
   disabled the run completes as a recorded no-op, `outcome: type_disabled`,
   with nothing written, as the other LLD skills do; a run that writes records
   `outcome: contract_written`, and `states.types` records the types it wrote.
4. **Documents only.** It writes:
   - the living **`<architecture_dir>/lld/<feature>/api/<interface>.md`**, one
     file per interface — a REST resource, a CLI command group, an event topic,
     a gRPC service — each opened with ADR-0122's front matter through
     `acs.py design init --type api-contract --feature <f>` for a new file and
     `design bump` for a changed one. Living documents are always shared;
   - the per-run record **`<architecture_dir>/lld/<feature>/<id>/api-contract.md`**
     (the run artifact `api-contract`, resolved as before), which summarises the
     change and links every interface file at its version. ADR-0132's
     share-or-keep-local choice applies to this record only.

   It never creates or edits the repo's machine-readable contract files:
   `contracts_mode`, the `<contracts_dir>` detection and the per-file-group
   slicing of those files go. Every path written is listed in `states.files`,
   and `/acs:create-pr` commits them in its `design` layer (ADR-0127).
5. **`/acs:code` makes the machine-readable files.** When the repo keeps
   OpenAPI, JSON Schema, proto or AsyncAPI files, `/acs:create-impl-plan`
   reads the approved contract (`artifacts show` plus `lld/<feature>/api/`) as
   an input and plans the items that create or update them from it; `/acs:code`
   implements those items like any other. `/acs:create-test-docs`,
   `/acs:create-e2e-tests`, `/acs:review-code` and `/acs:docs-sync` read the
   contract the same way.
6. **The loop matches the other Design skills.** The `contract-author` writes,
   sliced per interface with an integration pass only on a reported seam
   (ADR-0125); the `contract-reviewer` judges; a new read-only
   **`create-api-contract-gap-analyst`** runs in the same message as the survey
   — one per existing interface document, when the feature already has any —
   and classifies every gap between the document and the code as
   unimplemented, undocumented or drifted (ADR-0122). The review turn runs the
   $0 checks beside the judge: `acs.py design check` on every written api
   document, and the Mermaid and structure lints where data-design runs them.
7. **`api_surface` goes.** `/acs:analyze-requirements` no longer records an
   API-surface verdict, in its state or in the analysis `README.md`; where it
   finds an interface change, its report's next step says to design it with
   `/acs:create-api-contract`. The plan's `owes` block keeps `test_cases` and
   `e2e`.

## Consequences

- **Breaking.** `/acs:ship` no longer writes an API contract. A team that
  relied on it runs `/acs:create-api-contract` in Design, before the plan, for
  each interface the change touches; the plan then reads the approved contract.
- A repo's OpenAPI, JSON Schema, proto or AsyncAPI files change only through
  `/acs:code`, from plan items, where the code that serves them is built and
  tested in the same changeset.
- Old state still loads. An analysis published before this change that carries
  `api_surface:` validates — unknown front-matter keys are ignored, and the
  analysis state schema keeps the key as an optional, ignored property. A plan
  carrying `owes.api_contract` is accepted and the key ignored. A run that
  recorded `create-api-contract` as a ship step keeps that record; the cursor
  no longer asks for it.
- One more agent file (`create-api-contract-gap-analyst`), no new role kind:
  `gap-analyst` already exists. The step-gate no-op table loses
  `no_surface_owed`, and `/acs:review-code`'s lens C no longer has a "nothing
  owed" branch for the contract: it reads the contract when one exists.
- A feature's interfaces now have a living, versioned home that later tickets
  revise in place and `/acs:audit-design` can audit, as its data and flows
  already did.
- `/acs:docs-sync` still does not keep `lld/<feature>/` current after
  implementation (P7); a change that moves an interface is re-designed by
  re-running the skill.
