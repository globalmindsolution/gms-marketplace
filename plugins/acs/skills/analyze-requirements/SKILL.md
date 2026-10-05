---
name: analyze-requirements
description: Analyze requirements before anything is planned — from a ticket, a prompt, a PRD feature or an attached spec or document (PDF, image, markdown), or any mix of them — survey the codebase to map the impact across components/files/tests, clarify the open questions, assumed defaults and refined acceptance criteria with the user through the clarification ledger, then write, review and publish the analysis — a folder: a README.md readable on its own plus one file per bounded context the requirements touch — as the reusable record later skills and re-analyses start from — a PRD feature's living analysis, or the delivery run's own. Names the risks, the load-bearing surfaces and interfaces it touches and whether a design is needed; an interface change is pointed to /acs:create-api-contract. Use as the first step on a ticket, before /acs:create-impl-plan; to analyze a PRD feature, a spec or a requirement written in the prompt, with or without a ticket; and whenever the user asks what a ticket or a feature really changes, touches or risks, or wants its open questions and acceptance criteria pinned down before it is planned. Call it as your first action on such a request — do not Glob, Grep or Read for the ticket, documents, plan, run or repo files, and do not look for a shell: it locates all of them itself.
argument-hint: "[ticket-id] [documents…] [prompt]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:analyze-requirements. Your job: turn the
REQUIREMENTS in front of you into the analysis — a folder (ADR-0133) holding a
`README.md` anyone can read on its own (the scope and summary, the refined
acceptance criteria, the cross-cutting risks and decisions, the questions and
their answers, the verdict on whether the work is ready to be planned, and a
table of contexts) and one file per **bounded context** the requirements touch
(its impact map across components, files and tests, its rules and edge cases,
risks, open questions and API notes). The
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
tests, no repo docs other than the analysis folder (and the requirement refinements
the user confirms): `/acs:create-impl-plan` decides HOW the change is built,
and this analysis is what it plans from.

## Two modes — Discovery and Development

The same three stages run in both; what differs is what the analysis is OF and
where it is published (ADR-0129: Discovery is this skill and `/acs:create-prd`;
Development is the delivery pipeline `workflows/ship.yaml` drives):

| Mode | When | The analysis is of | Published to |
|---|---|---|---|
| **Discovery** | a standalone run with no ticket — a prompt, PRD feature docs, an attached spec | a PRD **feature**: everything the requirements say about it | `<prd_dir>/features/<feature>/analysis/` — the feature's **living analysis**, revised in place and versioned (ADR-0122 front matter: `status`, `version`, `tickets`, plus `feature`) |
| **Development** | the first step of a delivery run — a run on an implementation ticket, or a run `/acs:ship` drives on a prompt or documents | one change to that feature | `<development_dir>/<feature>/<ticket-id or run-id>/analysis/`, beside the run's later `plan.md` and `test-cases.md` |

Read `${CLAUDE_PLUGIN_ROOT}/skills/analyze-requirements/references/survey.md` (The mode and
the folders) before the `plan` action — how the mode is derived, the one case
the user overrides it, where `<prd_dir>` and `<development_dir>` come from,
and how a Development run starts from the feature's living analysis.
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
| **3 — Store: write, review and publish the analysis for reuse** | The `draft` action writes the analysis folder — README plus one file per context — from the notes and the answers; the `review` action judges it; the `publish` action copies it to the mode's path (Two modes, above) and leaves it uncommitted in the working tree. | analyst (`pass` = `draft`) → impact reviewer → the controller | the published analysis, an uncommitted change |

The survey never writes the draft and the draft pass never re-surveys: the
questions have to reach the user BETWEEN the two, so the draft is written from
answers rather than from guesses. The published folder is the reusable record —
the next skills plan from it, and the next run of this skill starts from it.

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step analyze-requirements --args "$ARGUMENTS"
```

If it exits non-zero: STOP and surface its stderr verbatim to the user. Do not
improvise a workaround — `${CLAUDE_PLUGIN_ROOT}/skills/analyze-requirements/references/blocked.md`
says what the gate checks, and what to do if an epic reaches this step anyway.

Parse the printed context JSON. Fields you will use:

- `requirements` — `{path, sources, acceptance_criteria, features, feature,
  needs_design, phase, feature_analysis}`: the run's requirements, normalised
  once per run from every container the invocation named
  (`acs_lib.requirements`); what each field holds is in `references/survey.md`.
  **Requirements: `context.requirements` /
  `acs.py requirements show` — a ticket id, documents and a prompt are only where they came from;
  never read ticket.json for acceptance criteria.**
- `ticket_id`, `ticket` — the ticket, when the invocation named one (`null`
  otherwise): its `type`, `docs_only`, `features`, `parent` and `external`. It
  is a container and a tracker, not the source of the requirements.
- `partition` — absolute path of the run partition. Phase artifacts go in
  `steps/analyze-requirements/`; the controller's state is
  `steps/analyze-requirements/loop.json`.
- `checkout_root` — the consumer repo root; every impact path in the analysis
  is repo-relative to it.
- `design` — `{required, dir, source}`: when `required`, the design that
  bounds the analysis, `<design_doc>` (`references/survey.md` resolves it).
- `agents` — the agent name to spawn per role (Subagents, below).
- `reconcile`, `handoff_summary`, `prior_status` — when `reconcile` is true or
  `handoff_summary` is set, read `${CLAUDE_PLUGIN_ROOT}/skills/analyze-requirements/references/resume.md`
  first: the reconcile procedure (the controller already knows which action
  the prior run reached). A fresh run skips it.

Throughout this file `<partition>` means the `partition` path from the context
JSON, `<id>` means `ticket_id` (e.g. `SHOP-123`) on a run that has a ticket,
and `<feature>` the feature slug. Every `--ticket <id>` below is passed only
when the run has a ticket; without one, `clarify.py` and `acs.py` resolve the
run from this checkout's pointer.

## Working tree — the analysis is a repo folder

The analysis is a folder in the consumer repo — at the mode's path (Two modes,
above), never a setting you choose. This skill never
creates, switches or names a branch, and never stages, commits or pushes
(ADR-0127): whatever is checked out stays checked out, and the published
analysis is left as an uncommitted change in the working tree, every path
written recorded in the result's `states.files` — unless the run keeps it
LOCAL (Stage 2, "Where the analysis goes"), when it stays in the run's state
folder and enters neither the repo nor a commit. `/acs:create-pr` is the only
skill that branches and commits — it splits the run's working-tree changes
into reviewable commits, the documents first.

### Analysis artifact resolution

The analysis is ONE folder per run's subject, named `analysis/`, on every run:
a `README.md` and one kebab-case `<context>.md` per bounded context (never an
`index.md`). Resolve where it lives before anything else:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" artifacts show
```

(The run comes from this checkout's pointer; `--run <run-id>` or `--ticket
<id>` names it explicitly.)

Read `${CLAUDE_PLUGIN_ROOT}/skills/analyze-requirements/references/survey.md` once it
has printed — what each key means (`<previous_analysis>`, `<feature_analysis>`,
the publish target), and a feature to record BEFORE the survey.

## Inputs — gather before the survey

Read these yourself and name them by path in the survey lanes' `<inputs>`
(never inline a file body). Each is read WHEN PRESENT — a missing one is not
an error, and the requirements alone are enough to analyze from: the seven
`references/survey.md` lists under The inputs, in order.

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
| `plan` | Declare the code areas, once (Survey lanes, in the fan-out reference). | `acs.py analysis plan --areas <a>,<b>` (empty → one impact lane over the whole repository; `--mode` only on the user's explicit ask, Two modes above) |
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

**`blocked`** never spends an iteration. Read `${CLAUDE_PLUGIN_ROOT}/skills/analyze-requirements/references/blocked.md`
when an action returns `blocked` — what each `kind` asks of you, and which
`record` verb to call again.

## Subagents — roles, spawning and messages

| Role | Agent | Kind | Spawn as | Runs in |
|---|---|---|---|---|
| analyst | `acs:analyze-requirements-analyst` | write | `context.agents.analyst` | `survey` (requirements lane), `synthesize`, `draft` |
| impact analyst | `acs:analyze-requirements-impact-analyst` | survey | `context.agents.impact-analyst` | `survey` (one lane per code area) |
| impact reviewer | `acs:analyze-requirements-impact-reviewer` | judge | `context.agents.impact-reviewer` | `review` (three judge slices) |

Decomposition of the survey into code areas is YOURS alone — subagents
never spawn subagents.

Read `${CLAUDE_PLUGIN_ROOT}/skills/analyze-requirements/references/fan-out.md` before you
spawn the first subagent — the passes and the cap, the one-message fan-out and
its slices, what every `<task>` and `<result>` carries, and how to spawn.

## Stage 1 — Impact: survey the codebase

The `survey` action: the analyst's requirements lane records what the
requirements ASK and one impact lane per code area what code they TOUCH, in
parallel, and the notes end with a `## Questions for the user` in four groups
(a)–(d) — the whole of what Stage 2 takes to the user. Read
`${CLAUDE_PLUGIN_ROOT}/skills/analyze-requirements/references/survey.md` (What the survey
records) before you spawn the lanes — what each lane records, and each group.

**Reuse the previous analysis.** When `<previous_analysis>` exists — and on a
Development run, `<feature_analysis>` — name it in every lane's `<inputs>`:
the survey starts from it instead of from nothing. Read
`${CLAUDE_PLUGIN_ROOT}/skills/analyze-requirements/references/reuse.md` when one exists —
what each lane re-verifies and carries forward, and the answers re-recorded
rather than asked again.

### The synthesis pass

The `synthesize` action. The join `record-survey` wrote is a join, not a
synthesis: this run MUST reconcile the lanes before anything is asked. Spawn
the ONE synthesis analyst the action names (`slice="synthesis"`,
`<constraint name="pass">synthesis</constraint>`) with the joined
`iter-1/authoring.md` in `<inputs>`. Read
`${CLAUDE_PLUGIN_ROOT}/skills/analyze-requirements/references/synthesis.md` when the
`synthesize` action is due — what the synthesis reconciles, how it settles
the contexts the analysis is split into, and what it writes.

## Stage 2 — Clarify: make the requirements clear with the user

The `clarify` action.

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list` (`--ticket <id>`
on a ticket run — the ticket's ledger; without a ticket the ledger is the
run's own, `runs/<run-id>/clarifications.json`) and reuse any recorded answer — re-asking an answered question is a defect.
Drop from the notes' `## Questions for the user` every question the ledger (or
the previous analysis, re-recorded as above) already answers.

**If nothing remains** — the survey produced no questions in any group, or the
ledger already answers all of them, and `docs where` (Where the analysis goes,
below) reports no `needs` — Stage 2 is skipped; say so in the report
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

### Where the analysis goes — share or keep local, in the same ask (ADR-0132)

Before Stage 2 asks anything, ask acs where the analysis will go:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" docs where --doc analysis.md
```

(`--doc living:prd` on a Discovery run: the feature's living analysis is
always shared, so only its folder can be in question.) Read `needs`:

- **empty** → the saved choice decides, silently: `share: true` publishes to
  the phase folder; `share: false` keeps the analysis LOCAL — in the run's
  state folder (`path`: `steps/analyze-requirements/local/analysis/`), where
  every later step still reads it through `acs.py artifacts show`, never in
  the repo and never in `/acs:create-pr`'s commits.

Read `${CLAUDE_PLUGIN_ROOT}/skills/analyze-requirements/references/clarify.md` when
`needs` is not empty — the `share` and `location` questions and how they are
saved — and when the run has no feature yet: naming or inferring it.

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
criteria stay a proposal in the analysis and an open ledger entry, and
`/acs:create-impl-plan` plans against the ticket as written (the requirements
as written, on a ticketless run).

### When the user is not reachable

Read `${CLAUDE_PLUGIN_ROOT}/skills/analyze-requirements/references/unreachable-user.md`
when this session cannot ask and no answers were relayed in a `/acs:ship`
brief — which defaults become assumptions, and which questions still block.

## Stage 3 — Store: write, review and publish the analysis for reuse

### Phase: analyst draft pass — `acs:analyze-requirements-analyst`

The `draft` action. Spawn ONE un-sliced analyst (`phase="analyst"`, no
`slice`, `<constraint name="pass">draft</constraint>`) with the action's
`notes` in `<inputs>` and every relevant `C-n` answer in `<context>`, plus
the mode and the feature as
`<constraint name="mode">discovery|development</constraint>` and
`<constraint name="feature"><slug></constraint>`. It
settles the whole-subject verdicts (interfaces changed, design significance) once,
from the reconciled notes plus the recorded answers — it does not re-survey —
and writes the analysis folder the action prints as `draft`
(`steps/analyze-requirements/iter-<n>/analysis/` — name it in the task's
`<inputs>`, with the action's `shape`; one draft per run, revised in place
across iterations, never renumbered) and its report `iter-<n>/analyst.json`.

Read `${CLAUDE_PLUGIN_ROOT}/skills/analyze-requirements/references/analysis-templates.md`
when the `draft` action is due — each file's exact front matter, headings and
sections (the analyst reads it too) — and `${CLAUDE_PLUGIN_ROOT}/skills/analyze-requirements/references/review-and-publish.md`
when it carries `findings` (iteration ≥ 2).

### Phase: impact reviewer — `acs:analyze-requirements-impact-reviewer`

The `review` action. Read `${CLAUDE_PLUGIN_ROOT}/skills/analyze-requirements/references/review-and-publish.md`
before you spawn its three judge slices in ONE message — what each is given,
the $0 checks beside it, and how `record-review` derives the verdict.

### Phase: publish — the controller is the only writer of the analysis

The `publish` action:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" analysis publish
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" analysis record-publication
```

`publish` refuses unless the last review passed and the draft is still the
exact bytes that review judged — bytes whose deterministic checks ran clean
beside that review, and unless the run has a feature (Stage 2, "The
feature"), and while `docs where` still reports `needs` it exits 2 naming
`acs.py docs decide` (Stage 2, "Where the analysis goes"). Copy
`publication.files` into your result's `states.files`. What `publish`
copies where, and who reads it next: `references/review-and-publish.md`.

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
       "questions_open": 0,
       "files": ["docs/development/wishlist/SHOP-123/analysis/README.md",
                 "docs/development/wishlist/SHOP-123/analysis/wishlist-sharing.md"]
     },
     "findings": [],
     "errors": []
   }
   ```

   Read `${CLAUDE_PLUGIN_ROOT}/skills/analyze-requirements/references/finish.md`
   before you write it — what each of the four `states` keys means and must
   equal, and what a failed run keeps.

2. Run the post-hook:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-analyze-requirements.py" --result-file "<the result.json you just wrote>"
   ```

   If it exits non-zero, surface its stderr verbatim — the run is not closed
   until it succeeds.

3. Report:
   - Direct invocation: a compact summary, then the Completion report below —
     `${CLAUDE_PLUGIN_ROOT}/skills/analyze-requirements/references/finish.md` lists what the summary covers.
   - Under `/acs:ship`: return ONLY the `<handoff>` XML as your final message —
     `status` matching result.json, `<summary>` ≤1 KB, `<artifacts>` naming the
     published analysis's README, `<questions>` when `needs_input`, and
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
- **Results**: verdict (ready_for_planning); contexts (one file each); impact map counts; interfaces changed; load-bearing surfaces named in Risks; questions asked/answered (or Stage 2 skipped); criteria / needs_design confirmed into the requirements (and the ticket); proposals still open; where the analysis went (shared to <path> / kept local (<your|team> default, or this run only))
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <uncommitted files written (the analysis folder's README and context files, repo-relative), partition phase artifacts>
- **Metrics**: iterations <n>/<cap> · <wall time>
- **Next**: `/acs:create-impl-plan <ticket-id>` on a Development run (the files stay uncommitted until `/acs:create-pr <ticket-id>`); the Design skills or `/acs:create-ticket` on a Discovery run; when an interface changes — design it with `/acs:create-api-contract <ticket-id or feature>` (Design phase) before the plan
```
