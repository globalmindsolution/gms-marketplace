# Inputs — what the planner is given

Read this once per run, before the planner is first tasked: the inputs you
read yourself and name by path in its `<inputs>`.

Read these yourself and name them by path in the planner's `<inputs>` (never
inline a file body):

1. The requirements — `requirements.path` from the context JSON (the run's
   `requirements.md`; the ticket, prompt and documents it was built from are
   only its containers).
2. The analysis when `acs.py artifacts show` reports it — `/acs:analyze-requirements`'s
   impact map, assumptions, risks and refined acceptance criteria — and the
   feature's living analysis (`feature_analysis`, the Discovery analysis of the
   feature in `<prd_dir>/features/<feature>/analysis/`) when it exists. An
   analysis is a folder (ADR-0133): `artifacts["analysis.md"]` is its
   `README.md` — scope, refined criteria, cross-cutting risks and a table of
   its bounded contexts — and `analysis_files` lists every file. Read the
   README first, then only the context files the plan touches; a legacy single
   `analysis.md` is read whole. Absent is not an error: plan from the
   requirements and the codebase instead, and say so in the plan.
3. `<design_doc>` when `design.required` — the decided architecture
   the plan must realize.
4. `<partition>/specs/*.md` when present (sorted `01-`, `02-`, ... — that is
   the dependency order). Absent or empty activates the spec authoring fold
   below.
5. The consumer repo: the source, tests and docs the change touches, plus the
   architecture doc set (`architecture_dir`) when the repo has one.

6. The API contract when `acs.py artifacts show` reports it —
   `artifacts["api-contract.md"]`, the run record `/acs:create-api-contract`
   publishes in the Design phase (ADR-0134), and the living interface
   documents it links under `<architecture_dir>/lld/<feature>/api/`. The
   approved contract is binding: the plan implements its shapes, error codes
   and compatibility decisions and never re-designs them. That skill writes
   documents only, so when the repo keeps machine-readable contract files
   (an OpenAPI document, JSON Schemas, `.proto`, AsyncAPI), creating or
   updating them from the contract is THIS plan's work: an executor task
   whose file map names them, in the format the repo already uses. Absent is
   not an error: an interface the requirements change with no contract is
   planned from the requirements and the code, and the plan says so.
