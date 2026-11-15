# Scope and inputs — what you find, and what the contract-authors read

Read this once per run, before the first contract-author is tasked: what you
find decides how you scope the run, and the inputs below are named by path in
every `<inputs>`.

## What you find decides the scope

What you find decides how you scope the run, never whether it runs:

- **The requirements** — always there (`requirements.path`, the run's
  `requirements.md`). Their acceptance criteria are the scope boundary: the
  contract covers exactly the interfaces they add, change or remove, and every
  item traces to one of them. A surface no criterion describes is out of scope,
  however tempting — the notes name it as excluded.
- **No plan is needed, and none is read as a boundary.** This is a Design
  skill (ADR-0134): it runs before `/acs:create-impl-plan`, which reads the
  approved contract as an input. A plan that already exists is never what the
  contract is scoped by, and no item traces to a plan item.
- **The analysis present** — its impact map, assumptions, refined acceptance
  criteria and API notes inform the survey. An older analysis may still carry
  an `api_surface:` front-matter key; it is ignored (ADR-0134) — the survey
  decides which interfaces change. Do not work around a stale analysis by
  editing it yourself: it is `/acs:analyze-requirements`'s artifact, re-run
  there.
- **The analysis absent** — the survey works from the requirements and the
  code alone. Say so in the run record's `## Scope & sources` and in the
  completion report.

## Inputs — gather before the loop

`acs.py artifacts show` (Start step 3) reports the run's documents and their
exact paths (`null` when one does not exist) — pass THOSE paths; do not
re-derive them. Name these by path in every contract-author's and gap
analyst's `<inputs>` (never inline a file body); an input that does not exist
is named as absent, never invented:

1. The requirements document (`requirements.path`) — the acceptance criteria
   every item traces to.
2. The feature's living analysis (`feature_analysis`,
   `<prd_dir>/features/<feature>/analysis/`) and the run's analysis when they
   exist. Each is a folder (ADR-0133): pass its `README.md`, then only the
   context files whose API notes touch an interface (`analysis_files`); a
   legacy single `analysis.md` is read whole.
3. The run's `tech-design.md` (`artifacts["tech-design.md"]`) when it exists — interface
   decisions the design already settled are binding; the contract renders
   them, never re-opens them.
4. The HLD: `hld/integration-map.md` (who exposes and consumes which API, sync
   or async — the landscape each interface document details),
   `hld/cross-cutting.md` (the API conventions: versioning, error envelope,
   naming, pagination, authentication), `hld/tech-stack.md`,
   `hld/c4-container.md`.
5. The feature's existing `lld/<feature>/api/*.md` documents — revised in
   place, never duplicated — and its `lld/<feature>/data/*.md` documents (the
   entities and fields the shapes expose must agree with them), plus
   `lld/<feature>/flows/` when present.
6. The interfaces in code: the handlers, routers, parsers, emitters and
   public signatures that implement today's surface — the current shape is
   what "changed" is measured against. When the repo keeps machine-readable
   contracts (an OpenAPI document, JSON Schemas, `.proto` files), they are read
   as evidence of today's shape, never edited.

Any of 2-5 may be absent; the design is then grounded in the requirements and
the code as it is.
