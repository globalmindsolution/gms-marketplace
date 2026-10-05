---
name: analyze-requirements
description: Analyze requirements before anything is planned — from a ticket, a prompt, a PRD feature or an attached spec or document (PDF, image, markdown), or any mix of them — survey the codebase to map the impact across components/files/tests, clarify the open questions, assumed defaults and refined acceptance criteria with the user through the clarification ledger, then write, review and publish analysis.md as the reusable record later skills and re-analyses start from — a PRD feature's living analysis, or the delivery run's own. Names the risks, the load-bearing surfaces it touches and whether a design is needed; its api_surface flag decides whether an API contract is written. Use as the first step on a ticket, before /acs:create-impl-plan; to analyze a PRD feature, a spec or a requirement written in the prompt, with or without a ticket; and whenever the user asks what a ticket or a feature really changes, touches or risks, or wants its open questions and acceptance criteria pinned down before it is planned. Call it as your first action on such a request — do not Glob, Grep or Read for the ticket, documents, plan, run or repo files, and do not look for a shell: it locates all of them itself.
argument-hint: "[ticket-id] [documents…] [prompt]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:analyze-requirements. Your job: turn the
REQUIREMENTS in front of you into `analysis.md` — the problem restated, the
impact map across components, files and tests, the questions the requirements
leave open and their answers, the assumptions and risks, refined acceptance
criteria, and a verdict on whether the work is ready to be planned. The
requirements come from the user; a ticket id, documents (in the repo, or
attached from outside it — a PDF, an image, a markdown spec) and a prompt are
only the containers they arrived in, and one invocation may mix them:
`/acs:analyze-requirements SHOP-12 ~/Downloads/spec.pdf "also bulk export"`.
**No ticket is required** (ADR-0128). You orchestrate three subagents over XML —
an **analyst** that records what the requirements ask and, in later passes,
reconciles the survey and writes the analysis draft; one **impact analyst** per
code area that maps what code the requirements touch; and an **impact reviewer**
that re-derives the impact map and judges the draft fresh
(analyst → impact review); you never write the analysis content yourself. The one thing you do
yourself is talk to the user.

**A controller runs the loop, not you (ADR-0114).** `acs.py analysis next`
prints exactly ONE action; you perform it and report it with the matching
`acs.py analysis record-*` verb; then you ask `next` again — until it says
`completed`, `blocked` or `failed`. The controller decides which pass runs
next, when the survey needs a synthesis, whether an iteration passed (it
reads the judges' `<result>` snapshots itself), when the loop has stalled or
spent its cap, and it publishes. You never advance the loop on your own
reading, and you never hand it a verdict.

You analyze; you never implement and you never plan. No production code, no
tests, no repo docs other than `analysis.md` (and the requirement refinements
the user confirms): `/acs:create-impl-plan` decides HOW the change is built,
and this analysis is what it plans from.

`analysis.md` is read by machines as well as people. Its front-matter
`api_surface` is what `workflows/ship.yaml`'s `api_surface_changed` predicate
and the `/acs:create-api-contract` gate read to decide whether an API contract
is written for this change at all — so the front matter is part of the
deliverable, not decoration.

## Two modes — Discovery and Development

The same three stages run in both; what differs is what the analysis is OF and
where it is published (ADR-0129: Discovery is this skill and `/acs:create-prd`;
Development is the delivery pipeline `workflows/ship.yaml` drives):

| Mode | When | The analysis is of | Published to |
|---|---|---|---|
| **Discovery** | a standalone run with no ticket — a prompt, PRD feature docs, an attached spec | a PRD **feature**: everything the requirements say about it | `<prd_dir>/features/<feature>/analysis.md` — the feature's **living analysis**, revised in place and versioned (ADR-0122 front matter: `status`, `version`, `tickets`, plus `feature`) |
| **Development** | the first step of a delivery run — a run on an implementation ticket, or a run `/acs:ship` drives on a prompt or documents | one change to that feature | `<development_dir>/<feature>/<ticket-id or run-id>/analysis.md`, beside the run's later `plan.md` and `test-cases.md` |

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
Both modes need a **feature**: a ticket's first `features` slug, the feature
the requirements name, or — when neither does — the one the user picks in
Stage 2's grouped ask (Stage 2, "The feature").

## Three stages

Every run is three stages, in this order — each finishes before the next
starts (the controller enforces the order):

| Stage | What happens | Who | Ends with |
|---|---|---|---|
| **1 — Impact: survey the codebase** | The `survey` action: the analyst's requirements lane and one impact lane per code area run in parallel and record what the requirements ask and what code they touch, ending in a `## Questions for the user` section; the `synthesize` action reconciles the lanes. | analyst (`pass` = `requirements`, then `synthesis`) · impact analysts | `iter-1/authoring.md` |
| **2 — Clarify: make the requirements clear with the user** | The `clarify` action: you ask every remaining question — the feature too, when the run has none — in ONE grouped AskUserQuestion, record each answer in the ledger, and record the confirmed acceptance criteria / `needs_design` / feature with `acs.py requirements refine` (which amends the ticket when there is one). | you | answers in the ledger; the requirements refined |
| **3 — Store: write, review and publish the analysis for reuse** | The `draft` action writes `analysis.md` from the notes and the answers; the `review` action judges it; the `publish` action copies it to the mode's path (Two modes, above) and leaves it uncommitted in the working tree. | analyst (`pass` = `draft`) → impact reviewer → the controller | the published analysis, an uncommitted change |

The survey never writes the draft and the draft pass never re-surveys: the
questions have to reach the user BETWEEN the two, so the draft is written from
answers rather than from guesses. The published file is the reusable record —
the next skills plan from it, and the next run of this skill starts from it.

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step analyze-requirements --args "$ARGUMENTS"
```

`--args` is the invocation's raw argument text — the ticket id, document paths
and prompt, in any order and any mix. `step start` parses it into the run's
sources (a `<PREFIX>-<n>` token is a ticket, a token naming an existing file is
a document, everything else is the prompt), copies a document from outside
the repo into the run and hashes it, and writes the run's `requirements.md`;
on a host whose Skill pre-hook already did this it is idempotent.

If it exits non-zero: STOP and surface its stderr verbatim to the user. Do not
improvise a workaround (`pre-analyze-requirements.py` checks only the safety
brakes: a ticket, when the invocation names one, resolves to a live, unlocked
partition and is not an epic — an epic is designed and fanned out, never
analyzed as one ticket. Nothing
upstream is required: no predecessor-completed check exists, because the
pipeline order lives in `workflows/ship.yaml`, not in this gate — this skill
works from the requirements themselves and reads the design and product docs
only when they exist, whether `/acs:ship` invoked it or a user did).

Parse the printed context JSON. Fields you will use:

- `requirements` — `{path, sources, acceptance_criteria, features, feature,
  needs_design, phase, feature_analysis}`: the run's requirements, normalised
  once per run from every container the invocation named
  (`acs_lib.requirements`). `path` is the run's
  `requirements.md` — the ticket's title, description and acceptance criteria
  numbered `AC-1…`, the prompt verbatim, each document inlined (markdown,
  text) or cited by its run copy under `<run>/subject/` (a PDF or an image:
  Read that copy), and a `## Refined` section only `acs.py requirements
  refine` writes. `sources` lists the containers (`ticket` / `document` /
  `prompt`); `feature` is the feature this analysis is filed under once one is
  known (refined, else the ticket's first `features` slug); `phase` is the
  mode — `development` when the run has a ticket or `/acs:ship` drives it,
  else `discovery` (Two modes, above); `feature_analysis` is the feature's
  living analysis when one exists. **Requirements: `context.requirements` /
  `acs.py requirements show` — a ticket id, documents and a prompt are only where they came from;
  never read ticket.json for acceptance criteria.** A later invocation that
  names new containers adds them (`acs.py requirements add --args "…"`), and
  `requirements.md` is regenerated, never edited by hand.
- `ticket_id`, `ticket` — the ticket, when the invocation named one (`null`
  otherwise): its `type`, `docs_only`, `features`, `parent` and `external`. It
  is a container and a tracker, not the source of the requirements.
- `partition` — absolute path of the run partition. Phase artifacts go in
  `steps/analyze-requirements/`; the controller's state is
  `steps/analyze-requirements/loop.json`.
- `checkout_root` — the consumer repo root; every impact path in the analysis
  is repo-relative to it.
- `design` — `{required, dir, source}`. `design.dir` is the PARTITION of the
  ticket whose design applies (`source` is `"own"` or `"parent"`); its
  basename is that ticket's id. When `design.required` is true, resolve the
  design document itself with `acs.py artifacts show --ticket <that id>` and
  read `artifacts["design.md"]`. Call it `<design_doc>`; the analysis is
  bounded by a design that already exists, never a second opinion on it.
- `agents` — the agent name to spawn per role; the analyst's, impact analysts'
  and impact reviewer's model and effort come from
  `settings.models.analyze-requirements.<role>` (inheriting when unset).
- `reconcile`, `handoff_summary`, `prior_status` — see
  `references/resume.md`.

Throughout this file `<partition>` means the `partition` path from the context
JSON, `<id>` means `ticket_id` (e.g. `SHOP-123`) on a run that has a ticket,
and `<feature>` the feature slug. Every `--ticket <id>` below is passed only
when the run has a ticket; without one, `clarify.py` and `acs.py` resolve the
run from this checkout's pointer.

**Epics are refused by the gate.** Every ticket that reaches this step has
`ticket.type != "epic"`. If an epic reaches it anyway (a bypassed or
best-effort pre-gate on some runtime), STOP and surface the same message the
gate would have raised: design the epic with `/acs:create-design <id>`, fan it
out with `/acs:create-ticket <id>`, then run `/acs:analyze-requirements` on a child.

## Working tree — the analysis is a repo file

`analysis.md` is a file in the consumer repo — at the mode's path (Two modes,
above), never a setting you choose. This skill never
creates, switches or names a branch, and never stages, commits or pushes
(ADR-0127): whatever is checked out stays checked out, and the published
analysis is left as an uncommitted change in the working tree, every path
written recorded in the result's `states.files`. `/acs:create-pr` is the only
skill that branches and commits — it splits the run's working-tree changes
into reviewable commits, the documents first.

### Analysis artifact resolution

`analysis.md` is ONE file per run's subject, one name, on every run. Resolve
where it lives before anything else:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" artifacts show
```

(The run comes from this checkout's pointer; `--run <run-id>` or `--ticket
<id>` names it explicitly.)

- `artifacts["analysis.md"]` non-null → that existing file is the analysis:
  the PREVIOUS analysis of this subject (on a Discovery run, the feature's
  living analysis itself). Stage 1's survey starts from it (reuse — see Stage 1),
  and this run REVISES it in place (a re-analysis after new information,
  never a second file). Call it `<previous_analysis>`.
- `paths["analysis.md"]` non-null → where this run publishes: the mode's path
  (the feature root on a Discovery run, `docs_dir` — the Development folder
  — otherwise). It is null until the run has a feature.
- no checkout to anchor the docs folder to → the analysis is published to the
  run partition's `analysis.md` — the partition fallback, for the no-checkout
  case only.

On a Development run, `feature_analysis` names the feature's living analysis
(`<prd_dir>/features/<feature>/analysis.md`) when it exists: a second reuse
input, read and never written. Call it `<feature_analysis>`.

A run with no feature yet cannot resolve a previous analysis. When the
invocation itself names the feature — the prompt says which ("the order
tracking feature"), or a PRD feature document is among the sources — that is
the user's answer already: record it in the ledger and with `acs.py
requirements refine` (`{"feature": "<slug>"}`, Stage 2's "The feature"), then
resolve again, BEFORE the survey, so it starts from the feature's living
analysis. Otherwise the requirements lane reads the living analysis of each
candidate feature it proposes (`<prd_dir>/features/<slug>/analysis.md`, when
present).

A legacy `docs/tickets/<id>/analysis.md` from before ADR-0128 is still READ
(it is the previous analysis when the new folder has none); nothing writes
there any more — the revision is published to `paths["analysis.md"]`. This is exactly what `acs_lib.artifacts.artifact_path`
resolves, what `acs.py analysis publish` writes to, and what the
`/acs:create-api-contract` gate looks for, so the path this run publishes is
the path that opens the next gate. A run with no feature yet has no folder to
publish to: `publish` refuses until Stage 2 records one.

The working draft lives at `steps/analyze-requirements/analysis.md`;
the published file is a copy of those exact bytes (see the `publish` action).

## The two references, and when to open each

Nearly all of this skill is one flow: survey, clarify, store. Two parts are
not, and each is read by exactly one kind of run:

| Open | When |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/skills/analyze-requirements/references/resume.md` | `context.reconcile` or `context.handoff_summary` is set. It carries the reconcile procedure; the controller already knows which action the prior run reached. A fresh run skips it. |
| `${CLAUDE_PLUGIN_ROOT}/skills/analyze-requirements/references/not-ready-for-planning.md` | `next` returns `blocked` with `kind: "needs_input"` and the question cannot be settled — still open after Stage 2's follow-up round, or the user is unreachable and a question genuinely blocks (no default could settle it without risking the wrong build). It carries the `ready_for_planning: false` / `needs_input` procedure. Most analyses never open it, and that is the intended outcome. |

## Inputs — gather before the survey

Read these yourself and name them by path in the survey lanes' `<inputs>`
(never inline a file body). Each is read WHEN PRESENT — a missing one is not
an error, and the requirements alone are enough to analyze from:

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
   components those docs name, and the code areas you declare (below) are
   the components they separate.
5. The consumer repo itself: the source, tests, docs and configuration the
   requirements touch. The impact map is derived from the CODE, not from the
   requirements' prose.
6. The clarification ledger (`clarify.py list`, `--ticket <id>` on a ticket
   run; a ticketless run's ledger is the run's own) — answers already
   recorded are inputs, not questions to ask again.
7. `<previous_analysis>` when `artifacts["analysis.md"]` exists — the last
   published analysis of this subject — and, on a Development run,
   `<feature_analysis>`, the feature's living analysis. The survey starts from
   them rather than from nothing, and re-verifies them against the current
   code (Stage 1).

## The controller loop

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" analysis next
```

`next` is read-only: run it as often as you like. It prints one JSON object
whose `action` is one of `plan`, `survey`, `synthesize`, `clarify`, `draft`,
`review`, `publish`, `completed`, `blocked` or `failed`, with the `iteration`
and every path the action involves — each agent's task attributes, the notes,
report and `<result>` snapshot it must produce, and the `record` command that
reports it. Use the paths it prints; never derive them yourself. Then:

| `action` | You do | Then report with |
|---|---|---|
| `plan` | Declare the code areas, once (Survey lanes below). | `acs.py analysis plan --areas <a>,<b>` (empty → one impact lane over the whole repository; `--mode` only on the user's explicit ask, Two modes above) |
| `survey` | Spawn every lane in `lanes` in ONE message (Stage 1). | `acs.py analysis record-survey` |
| `synthesize` | Spawn the one synthesis analyst it names (Stage 1). | `acs.py analysis record-synthesis` |
| `clarify` | Stage 2: ledger first, then one grouped ask. | `acs.py analysis record-clarify` — add `--blocking-open` when a question that blocks planning is still open |
| `draft` | Spawn the one draft-pass analyst, with `findings` verbatim in `<context>` (Stage 3). | `acs.py analysis record-draft` |
| `review` | Spawn the three judge slices in `slices` in ONE message (Stage 3). | `acs.py analysis record-review` |
| `publish` | Run its `commands` in order: `acs.py analysis publish`, then `acs.py analysis record-publication`. | — |
| `completed` | Finish, `status: completed`. | — |
| `blocked` | See below. | the `record` verb of `retry_action` |
| `failed` | Finish, `status: failed`: `stop_reason` (`stalled` or `cap`) and `reason` in the summary, `findings` in the result's `findings`. | — |

Every `record-*` verb prints the next action under `next`, so you rarely need
a separate `next` call. Each reads the snapshots and artifacts ITSELF: you
pass no verdict, no finding count and no path.

**`blocked`** never spends an iteration. Read `kind` and `reason`:

- `machinery` — a `<result>` snapshot is missing or malformed, carries the
  wrong `skill`/`phase`/`iteration`/`slice`, or an artifact the action owes is
  missing. The reason names the file. Re-run ONLY the agent(s) whose evidence
  is missing — once, with the reason quoted in the task — then call the same
  `record` verb again. On a host that does not fire SubagentStop, write the
  `<task>` and `<result>` to the snapshot path yourself before recording.
  Still blocked → finish `failed` with the reason in `errors`.
- `agent_failed` — an agent returned `status="failed"`. Supply what its
  `<error>`s say is missing and re-run it once; otherwise finish `failed`.
- `needs_input` — a question only the user can settle. When an agent
  returned `needs_input`, `retry` is `clarify`: take the questions in
  `reason` through Stage 2 (ledger first, one grouped ask), then
  `record-clarify`; the draft pass then re-runs on the SAME iteration. If the
  question cannot be settled, record it with `record-clarify --blocking-open`
  and open `references/not-ready-for-planning.md`. After a `--blocking-open`
  run the loop still drafts, reviews and publishes the not-ready analysis,
  and ends `blocked` with `kind: "needs_input"` and `retry: null` — finish
  `interrupted` with `stop_reason: "needs_input"`.

## Subagents — roles, spawning and messages

| Role | Agent | Kind | Spawn as | Runs in |
|---|---|---|---|---|
| analyst | `acs:analyze-requirements-analyst` | write | `context.agents.analyst` | `survey` (requirements lane), `synthesize`, `draft` |
| impact analyst | `acs:analyze-requirements-impact-analyst` | survey | `context.agents.impact-analyst` | `survey` (one lane per code area) |
| impact reviewer | `acs:analyze-requirements-impact-reviewer` | judge | `context.agents.impact-reviewer` | `review` (three judge slices) |

**Every analyst task names its pass** in
`<constraint name="pass">requirements|synthesis|draft</constraint>` — the
`pass` field of the action. No third role plans the analysis (ADR-0092: when
the deliverable is the analysis, a plan for it is a second copy of the work):
the survey records what the requirements ask and touch in the authoring notes,
you settle its questions with the user, the draft pass authors the analysis
from both, and the impact reviewer re-derives the impact map from the
repository and judges the result fresh. The cap is a fixed **3**
on every run — `/acs:analyze-requirements` has no path-driven verify depth —
and the controller counts it: one iteration is one draft → review cycle, not
a lane.

Decomposition of the survey into code areas is YOURS alone — subagents
never spawn subagents.

### Parallelism — survey lanes and judge slices

Every fan-out is yours: spawn the N instances in ONE message (all foreground,
in the same message), wait for all of them, and only then call the `record`
verb. At most `settings.parallel.max_agents` (default 4) instances run per
message; beyond that, run the rest in waves of that size.

**Writer — one analyst, never sliced.** `analysis.md` is a single document:
there is no disjoint-file partition of the deliverable, so one analyst writes
the draft on every iteration — and with one writer there is no integration
pass to run. What fans out is the survey (Stage 1) and the judge (Stage 3).

**Survey lanes.** Declare the code areas ONCE, with `acs.py analysis plan`,
by this rule: when the requirements' candidate impact spans **two or more disjoint
top-level areas** of the repo (top-level packages, services or apps: the
directories the architecture set, or failing that the repo root, names as
separate components), name each area by its directory basename (`api`, `web`,
`billing`); an area is a set of top-level directories and no directory belongs
to two areas, so no two slices survey the same path. A ticket inside one area
declares none, and gets one impact lane over the whole repository. The
analyst's requirements lane always runs beside them, so every survey has at
least two lanes and is always reconciled by a synthesis pass.

Each impact lane's task is `<task skill="analyze-requirements"
phase="impact-analyst" slice="<area>" …>` carrying
`<constraint name="survey_area"><the area's top-level paths></constraint>`
(the whole repository for the `repo` lane); it writes ONLY its
`iter-1/authoring-<area>.md` and `iter-1/impact-analyst-<area>.json`. The
requirements lane is `<task skill="analyze-requirements" phase="analyst"
slice="requirements" …>` with `<constraint name="pass">requirements</constraint>`.
`record-survey` joins every lane's notes into `iter-1/authoring.md`;
`record-synthesis` joins the synthesis last. Every lane's questions reach the
user in ONE grouped clarification-ledger ask (Stage 2), never one ask per lane.

**Judge slices.** The impact reviewer has seven check dimensions, so it
always runs as three slices, each a fresh instance of
`acs:analyze-requirements-impact-reviewer` whose task carries `slice="<id>"`
and `<constraint name="dimensions">` naming the dimension numbers it owns —
exactly the `slices` the `review` action prints:

| Slice | Dimensions | Owns the run of |
|---|---|---|
| `surface` | 2 `completeness`, 3 `api-surface` | the re-derivation of the impact surface from the repository, and the questions/ticket coverage check |
| `form` | 4 `front-matter`, 5 `structure`, 6 `scope` | `front_matter_check.py` and `structure_lint.py` |
| `evidence` | 1 `grounding`, 7 `authoring-conformance` | re-opening every citation in the notes and the draft |

Grounding policing applies in every slice. Each writes
`iter-<n>/impact-reviewer-<slice>.md`; `record-review` joins them, in the
table's order, into `iter-<n>/impact-reviewer.md`, drops exact duplicates
(same dimension, file and text) under a `## De-duplicated findings` section,
and derives the verdict: the iteration passes only if EVERY slice returned
`status="completed"` with zero blocking findings — never "pass with a missing
slice". A failed iteration's blocking findings are the next `draft` action's
`findings`; a set identical to the previous iteration's ends the run
`stalled` instead of spending another draft pass.

### Messaging rules (`the SubagentStop hook's message check`)

- Send each subagent one `<task skill="analyze-requirements"
  phase="analyst|impact-analyst|impact-reviewer" ticket-id="<id>"
  iteration="n">` — the `phase` is the role; `ticket-id` only when the run has
  a ticket — carrying `<objective>`, `<inputs>` (file refs) and
  `<constraints>`. The subagent returns a
  `<result>` with the same `phase` as its final content. A sliced instance's
  task and result also carry `slice="<id>"` (the action's `slice`); the draft
  pass omits it.
- Every phase's `<constraints>` carry `required_sections` (the seven headings
  below) and `<constraint name="audience_style_profile">implementers (evidence
  + impact narrative)</constraint>`; every analyst task also carries
  `<constraint name="pass">`.
- The SubagentStop hook checks each returned `<result>`'s `skill=`, `phase=`
  and `iteration=` (and `slice=` when sliced) and snapshots it to the
  action's `snapshot` path — `steps/analyze-requirements/iter-<n>/<phase>-message.xml`,
  or `iter-<n>/<phase>-<slice>-message.xml` for a slice. The controller reads
  only those snapshots; if one is missing (a host that does not fire the
  hook), write the `<task>` and `<result>` there yourself. Never write a
  message over an agent's own report.
- Spawn subagents with the Agent tool: `subagent_type:
  "acs:analyze-requirements-analyst"`, `"acs:analyze-requirements-impact-analyst"`
  and `"acs:analyze-requirements-impact-reviewer"` — the action's `agent` —
  falling back to the un-namespaced name only if the runtime rejects the
  namespaced one. Spawn each role under the name in
  `context.agents.<role>` — the plugin's `acs:analyze-requirements-<role>`, or the
  generated `acs-analyze-requirements-<role>` copy `acs step start` wrote where
  `settings.models` sets a model or effort for it. Model and effort travel with
  that agent, so pass none of your own. If the runtime rejects the agent, FAIL
  the run with that exact error — no silent fallback.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops (`for i in $(seq 1 40); do
sleep 15; done` and its kin), which wait a fixed ten minutes whatever the
agent did and spent a whole 1800s setup on the 2026-09-15 release gate.

## Stage 1 — Impact: survey the codebase

The `survey` action. The requirements lane (`phase="analyst"`
`slice="requirements"`, `<constraint name="pass">requirements</constraint>`)
records, from the requirements (`requirements.md` and the documents it
cites), the design when one binds, the product docs and the ledger, what the
requirements ASK: the problem against the code, which acceptance criteria are
ambiguous or untestable as written (or missing, when a prompt or a document
states behaviour as prose and no criterion yet), the design significance, the
PRD feature the work belongs to, the risks in the requirements, and the
questions for the user. Each impact lane (`phase="impact-analyst"`
`slice="<area>"`) records what code the requirements TOUCH in its area: the candidate impact surface (components, files, tests,
configuration) with a `path:line` citation for each entry, the API-surface
evidence, the code risks and the seams into other areas. The notes are what
the impact reviewer checks the draft against; a draft with no notes is a
blocking finding. No lane writes the draft.

**Reuse the previous analysis.** When `<previous_analysis>` exists — and on a
Development run, `<feature_analysis>` — name it in every lane's `<inputs>`:
the survey starts from it instead of from nothing. The feature's living
analysis is the feature as a whole; a Development run narrows it to this change
and cites what it carries over. The impact lanes re-verify each of its
impact-map rows against the current code —
still true / changed / gone, each with the evidence — the requirements lane
carries forward its answered `C-n` entries (answers are never asked again),
and both record what changed since under a `## Changes since the last
analysis` section of the notes. An answer the previous analysis records but
the ledger lacks (a fresh workspace) is still a recorded answer: re-record it
verbatim with `clarify.py add … --answer` in Stage 2 rather than asking it
again.

**The survey ends with `## Questions for the user`**, in four groups — the
whole of what Stage 2 takes to the user:

- **(a) Open questions** the code and docs cannot answer — the answer changes
  the impact map, the acceptance criteria or the verdict. Each says what the
  analysis would proceed on if it stays unanswered, or that it blocks
  (every default could build the wrong thing).
- **(b) Conventional defaults** the analysis would assume — each phrased
  `Assumed: <default> — confirm or correct`.
- **(c) Proposed refined acceptance criteria** — the rewrite of each
  ambiguous, untestable or contradicted criterion, and each missing one.
- **(d) A needs_design recommendation**, when the survey has one, and the
  **feature**: a `features` correction when the PRD features the work touches
  differ from the requirements' `features`, and — when the run has no feature
  yet (`context.requirements.feature` null and no ticket `features`) — the
  PRD feature slugs it most likely belongs to, best first, or a new slug when
  none fits (slugs, `acs.py slug --text "<PRD feature name>"`; ADR-0120).

Researchable facts are never questions: the survey reads the code, the docs,
the ledger and the previous analysis instead. An empty group says `_None._`.

### The synthesis pass

The `synthesize` action. The join `record-survey` wrote is a join, not a
synthesis: this run MUST reconcile the lanes before anything is asked. Spawn
the ONE synthesis analyst the action names (`slice="synthesis"`,
`<constraint name="pass">synthesis</constraint>`) with the joined
`iter-1/authoring.md` in `<inputs>`. It reads every section across the
`<!-- slice: <id> -->` markers and, where two lanes' notes contradict each
other (a symbol one lane calls unused and another finds called, an
API-surface or design verdict the areas disagree on, one file claimed by two
seams, a criterion the requirements lane calls testable that an impact lane
shows the code contradicts), records the resolution with the evidence under a
`## Synthesis` section of the notes — or, when no source settles it, turns it
into a group-(a) question; it never silently picks one. It also de-duplicates
the lanes' `## Questions for the user` into ONE list, in the four groups. It
writes ONLY `iter-1/authoring-synthesis.md` and `iter-1/analyst-synthesis.json`,
and `record-synthesis` joins it last. In the joined `## Questions for the
user`, the `<!-- slice: synthesis -->` block is the de-duplicated list Stage 2
asks; the per-lane blocks above it stay as provenance. The impact reviewer
judges the synthesis (dimension 7), and the draft pass consumes these
reconciled notes — it does not reconcile slices itself.

## Stage 2 — Clarify: make the requirements clear with the user

The `clarify` action.

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list` (`--ticket <id>`
on a ticket run — the ticket's ledger; without a ticket the ledger is the
run's own, `runs/<run-id>/clarifications.json`) and reuse any recorded answer — re-asking an answered question is a defect.
Drop from the notes' `## Questions for the user` every question the ledger (or
the previous analysis, re-recorded as above) already answers.

**If nothing remains** — the survey produced no questions in any group, or the
ledger already answers all of them — Stage 2 is skipped; say so in the report
("Stage 2 skipped: no open questions") and run `record-clarify`.

**Otherwise ask EVERY remaining question, from all four groups, in ONE
grouped interaction** — a single AskUserQuestion containing all of them as a
numbered list, grouped (a)–(d), not serial round-trips; the questions of every
lane go in that one ask. Conventional defaults (b) are asked as confirmations
("Assumed: … — confirm or correct"), proposed criteria (c) and the
needs_design recommendation (d) as confirm / reject / amend, and the feature
(d) as a choice among the proposed slugs (The feature, below).

Record each answer as its own `clarify.py add` entry (one `C-<n>` per
question, `--source` preserved), BEFORE acting on it. Never skip a question,
merge two questions into one entry, or auto-answer outside the existing
`--source assumption --rationale "..."` rule. Record every Q&A — obtained
interactively or relayed in a `/acs:ship` brief — with
`clarify.py add --skill analyze-requirements --question "..." --answer "..."`
(plus `--ticket <id>` on a ticket run), and pass the relevant `C-n` entries
to subagents in `<context>`. A user who
answers "you decide" gets the default recorded as an assumption, with that as
its rationale.

**One follow-up round, at most.** If the answers raise new questions, ask them
in at most ONE more grouped AskUserQuestion, recorded the same way. Anything
still open after that is a blocker: `references/not-ready-for-planning.md`
carries what to do about it — report it with `record-clarify --blocking-open`.
Otherwise report the stage with `record-clarify`.

### The feature — named or inferred, in the same ask

Every analysis is filed under a PRD feature (Two modes, above). A ticket run
takes its ticket's first `features` slug; a run whose requirements name a
feature (`context.requirements.feature`, or a PRD feature document among the
sources) takes that one. Otherwise — a ticketless prompt or an attached spec,
or a ticket with no `features` — the feature is a group-(d) question in the
SAME grouped ask, never a separate round-trip: offer the PRD feature slugs the
survey proposed, best first (each from `acs.py slug --text "<PRD feature
name>"`), and a new slug derived the same way when none fits. Record the
answer in the ledger and then with `acs.py requirements refine` as
`{"feature": "<slug>"}` (below) — `acs.py analysis publish` refuses a run that
has no feature recorded, naming this step.

### Confirmed requirements are refined — and go into the ticket when there is one

A proposed refined acceptance criterion, a needs_design recommendation or a
`features` correction is a RECOMMENDATION until the user answers it — recorded
as a ledger question (`clarify.py add --skill analyze-requirements --question
"..."`) before it is acted on. Apply it ONLY on an explicit user answer, and
then only through the CLI that records it in the run's requirements and, when
the run has a ticket, patches and re-indexes the ticket too — so the
requirements every later skill plans from carry the clarified version:

```bash
printf '{"acceptance_criteria": ["...", "..."]}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" requirements refine --from -
```

(`needs_design`, `features`, the run's `feature` and — only on the user's
explicit ask — its `phase` are recorded the same way, as
`{"needs_design": true}`, `{"features": ["wishlist"]}`,
`{"feature": "wishlist"}` or `{"phase": "discovery"}`.) `refine` writes the
run's `## Refined` section of `requirements.md` (never edit it by hand) and, on a ticket run, applies the
same document to the ticket as a PATCH merged over it, so send the WHOLE
confirmed criteria list — the requirements' criteria (`AC-1…`) with each
confirmed rewrite applied and each confirmed missing criterion added. A
rejected proposal is recorded (its answer says so) and NOT applied. With no
user answer, leave the requirements and the ticket as they are: the refined
criteria stay a proposal in `analysis.md` and an open ledger entry, and
`/acs:create-impl-plan` plans against the ticket as written (the requirements
as written, on a ticketless run).

### When the user is not reachable

The user is unreachable when this session cannot ask — AskUserQuestion is not
available or returns nothing (a non-interactive run: `claude -p`, an eval, a
scheduled run) — and no answers were relayed in a `/acs:ship` brief. Then, and
only then:

**A question with a conventional default is an assumption, not a blocker.**
When the requirements' words plus the repository's conventions settle a detail
well enough that a competent implementer would not stop to ask — "prints"
means stdout; a credential check is exact and case-sensitive unless the
requirements say otherwise; argument counts the requirements never mention
are out of scope; an unspecified error path follows the codebase's existing pattern —
record the default as an assumption (`--source assumption --rationale
"..."`), state it in `## Assumptions`, propose the matching criterion rewrite
in `## Refined acceptance criteria`, and keep `ready_for_planning: true`. The
2026-09-15 release gate lost a two-line login ticket to exactly three such
defaults asked as blockers, on a run with nobody to answer them. When the user
IS reachable, the same defaults are asked — as confirmations, in the one
grouped ask — never silently assumed: an assumption is a finding for a human
to confirm, never a silent default.

Group (c) and (d) proposals stay open ledger entries and the requirements
and the ticket are left as they are — except a run's missing feature, which
is inferred, because nothing can be published without one: the best-matching
PRD feature slug, or a new slug from the requirements' subject when none
fits, recorded as an assumption (`--source assumption --rationale "..."`) and
then with `requirements refine` `{"feature": "<slug>"}`. A group-(a) question
with a fallback is recorded as an assumption on that fallback; one where every
default could build the wrong thing makes the work not plannable —
`record-clarify --blocking-open`, and
`references/not-ready-for-planning.md` carries what to do about it.

This skill is where the requirements' ambiguities are SUPPOSED to surface, so the
analysis's `## Questions` section and the ledger are the same set of facts in
two places: every question is a ledger entry, and `## Questions` in the
published analysis names each entry by its `C-n` id and its status, so the
next skill can see what is still open.

## Stage 3 — Store: write, review and publish the analysis for reuse

### Phase: analyst draft pass — `acs:analyze-requirements-analyst`

The `draft` action. Spawn ONE un-sliced analyst (`phase="analyst"`, no
`slice`, `<constraint name="pass">draft</constraint>`) with the action's
`notes` in `<inputs>` and every relevant `C-n` answer in `<context>`, plus
the mode and the feature as
`<constraint name="mode">discovery|development</constraint>` and
`<constraint name="feature"><slug></constraint>`. It
settles the whole-subject verdicts (API surface, design significance) once,
from the reconciled notes plus the recorded answers — it does not re-survey —
and writes the analysis draft to `steps/analyze-requirements/analysis.md` — one
draft per run, revised in place across iterations, never renumbered — and its
report `iter-<n>/analyst.json`, with EXACTLY this front matter and these seven
headings, in this order:

```markdown
---
ticket: SHOP-123
ready_for_planning: true
api_surface: true
needs_design_recommendation: false
---

# Analysis — SHOP-123: <ticket title>

## Problem restated
## Impact map
## Questions
## Assumptions
## Risks
## Refined acceptance criteria
## Verdict
```

On a run with no ticket the first key is `feature: <slug>` in place of
`ticket:`, and the title reads `# Analysis — <feature>: <subject>`. A
Discovery run's draft — the feature's living analysis — also opens with the
version keys of ADR-0122 before the four above: `status: proposed`, `version`
(the living analysis's `version` + 1, or `1` for the feature's first
analysis), `tickets` (carried over from the living analysis) and `feature`:

```yaml
---
status: proposed
version: 2
tickets: ["SHOP-120"]
feature: wishlist
ready_for_planning: true
api_surface: true
needs_design_recommendation: false
---
```

What each section carries is defined in `analyze-requirements-analyst.md`; the
contract that matters here is that `## Impact map` is a table whose first
column is a repo-relative path (that column is what the load-bearing-surface
step below reads), that the front-matter values agree with the sections
beneath them, and that the answers show: `## Questions` lists every `C-n`
with its answer or status, `## Refined acceptance criteria` states which
criteria were confirmed into the requirements (and so the ticket, when there
is one), and `## Assumptions` holds only what the user did not answer.

On iteration ≥ 2 the action's `findings` are the previous iteration's
blocking findings, verbatim: put them ALL in the draft pass's `<context>`; it
fixes every one and nothing else, recording them in `iter-<n>/authoring.md`.
A reviewer finding that is really a new question for the user — or a draft
pass that returns `needs_input` — goes through Stage 2 again (ledger first,
then one grouped ask) before the draft pass re-runs with the answers in
`<context>`: the controller blocks with `kind: "needs_input"` and hands you
`clarify` on the same iteration.

### Phase: impact reviewer — `acs:analyze-requirements-impact-reviewer`

The `review` action. Spawn the three slices it prints (Judge slices above) in
ONE message, each with `<inputs>` of the draft, the authoring notes (the
action's `notes`), the analyst report (`analyst_report`), `requirements.md`
(its `## Refined` section as Stage 2 left it) and, on a ticket run, the ticket
file, the clarification ledger, `design.md` when it binds, and the repo paths
the impact map names. Each judges fresh — never forward the
analyst's reasoning — the `surface` slice re-derives the impact map from the
codebase itself and checks that every `## Questions for the user` item was
answered in the ledger or carried as an open/assumed entry, and that the
confirmed criteria match the refined requirements (and the ticket). Each writes
`steps/analyze-requirements/iter-<n>/impact-reviewer-<slice>.md`. Then
`record-review`: the controller joins the reports into
`iter-<n>/impact-reviewer.md` and derives the verdict from the slices'
`<result>` snapshots plus the draft's deterministic checks (below) — never
conclude a pass yourself.

**The deterministic checks run beside the review.** `record-draft` runs the
two $0 checks on the draft as it records it — the same front-matter spec and
section list the `form` slice runs — so they are done before the review
spawns, not after it passes; the `review` action lists their findings as
`draft_checks`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/front_matter_check.py" \
  --require "ticket: str; ready_for_planning: bool; api_surface: bool; needs_design_recommendation: bool" \
  --ticket <id> "steps/analyze-requirements/analysis.md"

python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/structure_lint.py" \
  --sections "Problem restated; Impact map; Questions; Assumptions; Risks; Refined acceptance criteria; Verdict" \
  --ordered "steps/analyze-requirements/analysis.md"
```

(On a run with no ticket the spec names `feature: str` in place of
`ticket: str` and takes no `--ticket`; `record-draft` picks the spec from the
run — you never choose it. A Discovery draft's version keys are part of the
reviewed bytes, and the `form` slice checks them.)

`record-review` folds them into that iteration's blocking findings: a check
finding fails the iteration like a judge's blocking finding (it goes to the
next draft pass, or ends the run at the cap), never patched by you.

### Phase: publish — the controller is the only writer of `analysis.md`

The `publish` action:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" analysis publish
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" analysis record-publication
```

`publish` refuses unless the last review passed and the draft is still the
exact bytes that review judged — bytes whose deterministic checks ran clean
beside that review (above), and unless the run has a feature (Stage 2, "The
feature"). Then it copies the draft byte-for-byte to the resolved analysis
path — the feature's living analysis on a Discovery run,
`<development_dir>/<feature>/<ticket-id or run-id>/analysis.md` on a
Development run — reads it back, and records the paths it wrote as
`publication.files` in the loop, repo-relative. It never
stages, commits or pushes and refuses no branch (ADR-0127): the files are left
as uncommitted changes in the working tree, and `/acs:create-pr` reads those
recorded paths to make the documents commit, the first of the PR.
`record-publication` re-derives it from the working tree — the published bytes
are still the reviewed bytes — and completes the loop. Copy
`publication.files` into your result's `states.files`.

You never copy or commit the analysis yourself, and no subagent does: the
file-map write guard (`acs_lib/filemap.py`) denies any running `write`-kind
agent — the analyst included — a write under the run's document folders, because
these documents are precisely the control inputs an implementer is checked
against. The partition draft is workspace state and is never committed.

The front-matter check uses the same parser the gate and the
`api_surface_changed` predicate use, so a draft it accepts cannot be rejected
downstream for its front matter.

**The published file is the reusable record.** The run's
`analysis.md` is what `/acs:create-impl-plan`, `/acs:create-api-contract` and
`/acs:create-test-docs` read, and what the next run of this skill starts from
(Stage 1's reuse); the feature's living analysis is what the Design skills
(`/acs:create-architecture`, `/acs:create-data-design`, `/acs:create-flows`,
`/acs:create-design`) read and what every later Development run on the feature
starts from. The partition copy exists only for the no-checkout case,
where there is no docs folder to publish to.

### Load-bearing surfaces — name them in `## Risks`

The impact map is the first place anyone can see WHAT this change touches, and
that is the single strongest input to the delivery-path judgement /acs:ship
makes later from the plan (ADR-0095). Nothing here writes a rigor setting —
there is no `stakes` axis any more, and this skill does not classify — but the
analysis is where the evidence for that judgement is recorded.

So when the impact map reaches a surface the repo treats as load-bearing —
authentication or authorization, payments, a migration or any stored shape, a
public API other systems call, concurrency or ordering, anything the repo's own
architecture docs flag — say so explicitly in `## Risks`, naming the paths. A
risk entry that names a boundary is read by `/acs:create-impl-plan` (which
carries it into the plan's own Risks section) and then by whoever judges the
path, and it is what turns a one-file change into a `standard` or `complex`
run instead of a `trivial` one.

Prose, not a setting: what makes this work is that the risk is stated where a
reader will weigh it, not that a glob matched.

## Context pressure

If your context window is running low mid-run: do NOT burn the remainder on
work that would be lost. Flush in-flight soft context (user answers, settled
sections, gotchas) to `steps/analyze-requirements/handoff-context.md` — the
loop's position is already in `loop.json` — then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --summary "<done / in-flight / next / decisions>"
```

Tell the user the `continue_with` command it prints, and stop.

## Finish

MANDATORY final step — never skipped, also on failure or handoff:

1. Write `steps/analyze-requirements/result.json` per the
   result-document contract in INTERNALS.md:

   ```json
   {
     "status": "completed",
     "summary": "3 questions answered in one ask, 2 criteria confirmed into the ticket; impact reviewer passed on iteration 1; analysis published",
     "states": {
       "ready_for_planning": true,
       "api_surface": true,
       "questions_open": 0,
       "files": ["docs/development/wishlist/SHOP-123/analysis.md"]
     },
     "findings": [],
     "errors": []
   }
   ```

   Canonical `states` keys — EXACT names; `acs step finish` documents
   them and the next steps read them:
   - `ready_for_planning` (bool): the verdict. `false` is the `needs_input`
     arm, and `/acs:create-impl-plan` is what consumes it.
   - `api_surface` (bool): whether the change adds or alters an API surface.
     It MUST equal the published front matter's `api_surface` — that front
     matter is what `ship.yaml`'s `api_surface_changed` predicate and the
     `/acs:create-api-contract` gate actually read, and a result document that
     disagrees with it is a defect, not a second opinion.
   - `questions_open` (int): clarifications still unanswered in the ledger —
     the count `clarify.py list --open` (`--ticket <id>` on a ticket run)
     prints after this run.
   - `files` (array): every repo-relative path this run wrote and left
     uncommitted — the publish action's `publication.files` (the published
     analysis: the feature's living analysis on a Discovery run, e.g.
     `docs/product/features/wishlist/analysis.md`). `/acs:create-pr` commits
     them; empty when nothing was published.

   The needs_design recommendation is applied through its own CLI
   (`acs.py requirements refine`), so it belongs in
   `findings` and the completion report, not in `states`. On failure keep
   whatever is true: `ready_for_planning: false`, the open findings in
   `findings`, and the reason (`stalled`, the iteration cap, needs input) in
   `summary` — the `failed` action's `stop_reason` and `reason`, verbatim.

2. Run the post-hook:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-analyze-requirements.py" --result-file "<the result.json you just wrote>"
   ```

   If it exits non-zero, surface its stderr verbatim — the run is not closed
   until it succeeds.

3. Report:
   - Direct invocation: a compact summary — the verdict, the impact map's
     component/file/test counts, what changed since the previous analysis
     when there was one, whether an API surface changes, the questions asked
     and answered (or "Stage 2 skipped"), the feature it is filed under, the
     criteria and needs_design confirmed into the requirements (and the
     ticket), any proposal still awaiting the user, open questions, the
     uncommitted files it left in the working tree, and the next step — on a
     Development run `/acs:create-impl-plan <id>` (`/acs:create-pr <id>` later
     commits everything the Development steps wrote); on a Discovery run the
     Design skills that read the feature's analysis (`/acs:create-design`,
     `/acs:create-data-design <feature>`, `/acs:create-flows <feature>`) or
     `/acs:create-ticket` to turn it into delivery work.
   - Under `/acs:ship`: return ONLY the `<handoff>` XML as your final message —
     `status` matching result.json, `<summary>` ≤1 KB, `<artifacts>` naming the
     published analysis, `<questions>` when `needs_input`, and
     `<next-step>/acs:create-impl-plan <id></next-step>`.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed, interrupted,
or handed off — ends your final message with the standard block (INTERNALS.md
"Completion report"), rendered only AFTER the post-hook succeeded. Same labels,
same order, `none` where empty; under `/acs:ship` your final message is the
`<handoff>` XML instead — this report is for direct invocations:

```markdown
## /acs:analyze-requirements · <ticket-id or feature> · <status>

- **Requirements**: <ticket id — title (type)>, <documents>, <prompt>; feature <slug> (<Discovery|Development>)
- **Status**: <status> — <summary; `stop_reason` when interrupted or failed>
- **Results**: verdict (ready_for_planning); impact map counts; api_surface; load-bearing surfaces named in Risks; questions asked/answered (or Stage 2 skipped); criteria / needs_design confirmed into the requirements (and the ticket); proposals still open
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <uncommitted files written (the analysis path, repo-relative), partition phase artifacts>
- **Metrics**: iterations <n>/<cap> · <wall time>
- **Next**: `/acs:create-impl-plan <ticket-id>` on a Development run (the files stay uncommitted until `/acs:create-pr <ticket-id>`); the Design skills or `/acs:create-ticket` on a Discovery run
```
