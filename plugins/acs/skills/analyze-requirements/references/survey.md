# /acs:analyze-requirements — the survey: mode, inputs and the previous analysis

Open this before the `plan` action: how the run's mode and folders are
derived, what the context fields and the keys `acs.py artifacts show` prints
mean for this run, which inputs every survey lane is named, and what each
lane records. The questions the survey ends with are SKILL.md's Stage 1.

**Where the cross-references below point.** "Two modes", "Stage 1",
"Stage 2", "Stage 3" and "The feature" are SKILL.md's sections.

## The mode and the folders

A Development run **starts from the feature's living analysis** when one
exists: it is a Stage 1 reuse input, exactly like a previous analysis of the
same run (Inputs, item 7) — the survey re-verifies it against the current code
and narrows it to this change; it is never copied and never edited by this run.
`<prd_dir>` and `<development_dir>` are found deterministically
(`acs_lib.requirements.prd_dir` / `development_dir`: a settings key, then the
docs the repo already has, defaulting to `docs/product` and
`docs/development`) — you never guess them, and `acs.py artifacts show` and
`acs.py analysis publish` print the resolved paths. The mode is derived, never
chosen by you (`context.requirements.phase`); only when the user explicitly
asks for the feature's living analysis on a run that would be Development
(e.g. "analyze the wishlist feature as a whole", naming a ticket for context)
record it — `acs.py analysis plan --mode discovery` when you declare the
lanes, or `{"phase": "discovery"}` with `acs.py requirements refine`.

## The context fields, in full

In `context.requirements`, `path` is the run's
`requirements.md` — the ticket's title, description and acceptance criteria
numbered `AC-1…`, the prompt verbatim, each document inlined (markdown,
text) or cited by its run copy under `<run>/subject/` (a PDF or an image:
Read that copy), and a `## Refined` section only `acs.py requirements
refine` writes. `sources` lists the containers (`ticket` / `document` /
`prompt`); `feature` is the feature this analysis is filed under once one is
known (refined, else the ticket's first `features` slug); `phase` is the
mode — `development` when the run has a ticket or `/acs:ship` drives it,
else `discovery` (Two modes, above); `feature_analysis` is the feature's
living analysis when one exists. A later invocation that
names new containers adds them (`acs.py requirements add --args "…"`), and
`requirements.md` is regenerated, never edited by hand.

- `design` — `{required, dir, source}`. `design.dir` is the PARTITION of the
  ticket whose design applies (`source` is `"own"` or `"parent"`); its
  basename is that ticket's id. When `design.required` is true, resolve the
  design document itself with `acs.py artifacts show --ticket <that id>` and
  read `artifacts["design.md"]`. Call it `<design_doc>`; the analysis is
  bounded by a design that already exists, never a second opinion on it.

## Resolving the previous analysis

- `artifacts["analysis.md"]` non-null → the existing analysis: the folder's
  `README.md` (the key keeps its old name), with every file of the folder in
  `analysis_files`, README first. It is the PREVIOUS analysis of this subject
  (on a Discovery run, the feature's living analysis itself). Stage 1's survey
  starts from it (reuse — see Stage 1), and this run REVISES it in place (a
  re-analysis after new information, never a second folder). Call it
  `<previous_analysis>`.
- `paths["analysis.md"]` non-null → where this run publishes: the target
  folder's `README.md` (the feature root on a Discovery run, `docs_dir` — the
  Development folder — otherwise). It is null until the run has a feature.
- no checkout to anchor the docs folder to → the analysis is published to the
  run partition's `analysis/` — the partition fallback, for the no-checkout
  case only.

On a Development run, `feature_analysis` names the feature's living analysis
(`<prd_dir>/features/<feature>/analysis/README.md`) when it exists: a second
reuse input, read and never written. Call it `<feature_analysis>`.

A run with no feature yet cannot resolve a previous analysis. When the
invocation itself names the feature — the prompt says which ("the order
tracking feature"), or a PRD feature document is among the sources — that is
the user's answer already: record it in the ledger and with `acs.py
requirements refine` (`{"feature": "<slug>"}`, Stage 2's "The feature"), then
resolve again, BEFORE the survey, so it starts from the feature's living
analysis. Otherwise the requirements lane reads the living analysis of each
candidate feature it proposes (`<prd_dir>/features/<slug>/analysis/README.md`,
when present).

A legacy `docs/tickets/<id>/analysis.md` from before ADR-0128 is still READ
(it is the previous analysis when the new folder has none), and so is a
legacy single-file `analysis.md` in the phase folder from before ADR-0133;
nothing writes either any more — the revision is published as a folder to
`paths["analysis.md"]`. This is exactly what `acs_lib.artifacts.artifact_path`
resolves, what `acs.py analysis publish` writes to, and what the
`/acs:create-api-contract` gate looks for, so the path this run publishes is
the path that opens the next gate. A run with no feature yet has no folder to
publish to: `publish` refuses until Stage 2 records one.

## The inputs, in order

1. The requirements — `requirements.md` at `context.requirements.path`, and
   every document copy it cites (a PDF or an image under `<run>/subject/`,
   which the lanes Read themselves): the ticket's title, description and
   acceptance criteria, the prompt, the documents, in that order. When the
   run has a ticket, also its file (whatever `acs.py artifacts show` reports
   as `source_path`) for its type and parent.
2. `<design_doc>` when `design.required` — the decided architecture.
   The analysis maps the requirements onto that decision; it never re-opens it.
3. The PRD and the living requirements set when they exist — what the
   product already promises about this area, and the feature list the
   feature slug is chosen from (`<prd_dir>/prd.md`, the feature folders under
   `<prd_dir>/features/`). Locate them, and the architecture set below, the
   way any session finds a document: CLAUDE.md and whatever docs index it or
   the repo points at (e.g. `docs/README.md`), then a Glob/Grep by file name
   or content (`prd.md`, a `requirements/` folder, `hld/tech-stack.md`;
   conventionally under `docs/product/`, `docs/requirements/`,
   `docs/architecture/`). Not found → not an input.
4. The architecture doc set when it exists (`hld/`, `lld/flows/`,
   `lld/contracts.md`) — the components the impact map names are the
   components those docs name, and the code areas you declare (the `plan` action) are
   the components they separate.
5. The consumer repo itself: the source, tests, docs and configuration the
   requirements touch. The impact map is derived from the CODE, not from the
   requirements' prose.
6. The clarification ledger (`clarify.py list`, `--ticket <id>` on a ticket
   run; a ticketless run's ledger is the run's own) — answers already
   recorded are inputs, not questions to ask again.
7. `<previous_analysis>` when `artifacts["analysis.md"]` exists — the last
   published analysis of this subject, its README and every file in
   `analysis_files` — and, on a Development run,
   `<feature_analysis>`, the feature's living analysis. The survey starts from
   them rather than from nothing, and re-verifies them against the current
   code (Stage 1).

## What the survey records

The `survey` action. The requirements lane (`phase="analyst"`
`slice="requirements"`, `<constraint name="pass">requirements</constraint>`)
records, from the requirements (`requirements.md` and the documents it
cites), the design when one binds, the product docs and the ledger, what the
requirements ASK: the problem against the code, which acceptance criteria are
ambiguous or untestable as written (or missing, when a prompt or a document
states behaviour as prose and no criterion yet), the design significance, the
PRD feature the work belongs to, the risks in the requirements, the
candidate **contexts** the PRD features suggest, and the questions for the
user. Each impact lane (`phase="impact-analyst"` `slice="<area>"`) records what
code the requirements TOUCH in its area: the candidate impact surface
(components, files, tests, configuration) with a `path:line` citation for each
entry and the bounded context it belongs to, named in plain words, the
API-surface evidence, the code risks and the seams into other areas. The notes are what
the impact reviewer checks the draft against; a draft with no notes is a
blocking finding. No lane writes the draft.
