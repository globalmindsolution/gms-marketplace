# Scope and inputs — what you find, and what the contract-author reads

Read this once per run, before the first contract-author is tasked: what you
find decides how you scope the run, and the inputs below are named by path in
its `<inputs>`.

## What you find decides the scope

What you find decides how you scope the run, never whether it runs:

- `plan.md` present — **the primary input**; the contract covers exactly the
  surface this plan adds or changes.
- `plan.md` absent — work from the requirements: their acceptance criteria
  (whether a ticket, a prompt or documents carried them) and the code are the scope. Say so in
  `## Scope & sources` and in the completion report, where the pointer is
  "run /acs:create-impl-plan <id> first" for a contract scoped by a plan.
- the analysis present — its API-surface assessment (`api_surface` in its
  `README.md` front matter) and its evidence inform the survey. When it declares `api_surface: false` and you
  were invoked anyway, run: the contract-author's survey either finds the
  surface the analysis missed — report that disagreement — or finds none, and
  the run completes with `outcome: no_surface_owed`.
  Do not work around it by editing the analysis yourself — the analysis is
  `/acs:analyze-requirements`'s artifact; a stale one is re-run there.
- the analysis absent — the survey assesses the surface from the plan (or
  the subject) and the code alone.

## Inputs — gather before the loop

Name these by path in the contract-author's `<inputs>` (never inline a file
body); an input that does not exist is named as absent, never invented:

1. `plan.md` (the path `artifacts show` reported), when it exists — **the
   primary input**. The contract covers the surface THIS plan adds or changes:
   its executor tasks, file map and API/data-changes content are the scope
   boundary. A surface the plan does not touch is out of scope, however
   tempting. With no plan, the requirements' acceptance criteria are the boundary.
2. The analysis, when it exists — the API-surface assessment and its
   evidence, the impact map, the assumptions and the refined acceptance
   criteria — and the feature's living analysis (`feature_analysis`) when one
   exists. Each is a folder (ADR-0133): read its `README.md` first, then only
   the context files whose API notes touch the surface; a legacy single
   `analysis.md` is read whole.
3. The requirements document (`requirements.path`, the run's
   `requirements.md`) — the acceptance criteria every item traces to.
4. `<design_doc>` when `design.required` — interface decisions the
   design already settled are binding; the contract renders them, never
   re-opens them.
5. The architecture doc set when it exists: `<architecture_dir>/lld/contracts.md`
   and the `lld/flows/` diagrams for the touched flows.
6. The existing contract files under `<checkout_root>/<contracts_dir>/` when
   the repo keeps them, plus the code that implements today's surface (the
   handler, the parser, the emitter) — the current shape is what "changed" is
   measured against.
