---
name: create-requirements
description: Bootstrap or amend the consumer requirements/ doc set (functional + non-functional, one file per feature/item) — brownfield reverse-engineers it from the existing codebase (architecture-aware, code-cited, DRAFT), greenfield elicits it interactively, and amend augments only absent/ungrounded areas — shipped as a docs-only PR on its own delivery ticket. Use to bootstrap living requirements on an existing codebase, or to refresh the set after a gap is found. Call it as your first action on such a request — do not Glob, Grep or Read for the ticket, plan, run or repo files, and do not look for a shell: it locates all of them itself.
argument-hint: "[delivery-ticket-id to resume | focus notes]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-requirements. You produce or amend the
consumer `requirements/` doc set — one file per functional feature and one per
non-functional item, in the functional/non-functional layout `/acs:code`'s
living-requirements merge already writes into — wherever the repo already keeps
its requirements set, else at `docs/requirements/`, as `<requirements_dir>` with
its functional subfolder `<functional_dir>` and non-functional subfolder
`<non_functional_dir>` (`functional/` and `non-functional/` for a new set; an
existing set's own subfolder names are followed, never renamed — see Start).
You ship it yourself as a docs-only PR on a fresh delivery ticket —
`/acs:code` and `/acs:create-pr` are NOT involved. You
orchestrate three subagents — surveyor → author → review: a read-only surveyor
classifies the mode and outlines the DRAFT baseline, you confirm it with the
user, an author writes the area files, and a reviewer judges them fresh. You
never write requirement content yourself. Every phase fans out: the survey
runs as parallel surveyor slices over disjoint areas of the repo when a
brownfield or amend survey spans two or more of them, the write runs as one
author per area file from iteration 1 (the area files are disjoint), and the
review always runs as three parallel reviewer slices over disjoint check
dimensions.

## Start

MANDATORY first action. Pick the form by inspecting `$ARGUMENTS`:

- `$ARGUMENTS` contains a ticket id matching the repo prefix (e.g. `SHOP-1` — you are
  resuming an interrupted or handed-off delivery ticket):

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-requirements --ticket <ticket-id>
  ```

- Otherwise (fresh bootstrap or amendment — every run gets a NEW delivery ticket):

  Before calling `acs step start --allocate`, locate the repo's requirements set
  the way any session finds a document: CLAUDE.md and whatever docs index it or
  the repo points at (e.g. `docs/README.md`), then a Glob/Grep for a
  `requirements/` folder or requirement files by content. Found → that folder is
  `<requirements_dir>`, and its existing functional and non-functional subfolders
  — whatever the set names them — are `<functional_dir>` and
  `<non_functional_dir>`. Not found → `<requirements_dir>` = `docs/requirements`,
  `<functional_dir>` = `docs/requirements/functional`, `<non_functional_dir>` =
  `docs/requirements/non-functional`, the conventional default. Then detect
  whether this is an **amend** run by checking if `<functional_dir>` or
  `<non_functional_dir>` already holds files (a substantially-populated set).
  This mirrors the surveyor's amend definition (see Survey below).

  - **Amend mode with a usable `$ARGUMENTS` request**: pass a `--title` flag:

    ```bash
    python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-requirements --allocate \
      --title "Amend requirements: <≤~10-word summary of what changed>"
    ```

    A usable `$ARGUMENTS` request (mirrors create-prd's clarification C-2): after
    stripping any leading delivery-ticket id, `$ARGUMENTS` contains free text
    describing what the amendment covers from which a short (about 10 words or
    fewer) summary can be formed. An empty, whitespace-only, or ticket-id-only
    `$ARGUMENTS` is NOT usable — pass no `--title` and the built-in fallback applies.

  - **All other cases** (brownfield/greenfield bootstrap — the set is absent or
    sparse — or an amendment where `$ARGUMENTS` carries no usable request): pass
    no `--title`:

    ```bash
    python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-requirements --allocate
    ```

  `--allocate` creates the delivery ticket (type `task`, built-in title
  **"Product requirements doc set"**, `PRODUCT_TICKET_TITLES["create-requirements"]`,
  overridable via `--title`), its workspace partition, the `.lock`, the session
  pointer, and the `in_progress` run entry.

If `acs step start` exits non-zero: STOP and surface its stderr verbatim.

Parse the printed context JSON. Key fields: `partition`, `ticket_id`, `ticket`,
`settings` (`formats`), `models`,
`reconcile`, `handoff_summary`, `post_hook`.

Keep the free text of `$ARGUMENTS` (focus notes, amendment request): it is surveyor and author input.
`<requirements_dir>`, `<functional_dir>` and `<non_functional_dir>` are the
repo-relative paths every later section uses; on the resume form, locate them the
same way right after `acs step start`.

## Resume & reconcile

If `context.reconcile` is true, verify recorded progress against reality BEFORE
continuing:

1. Re-read `steps/create-requirements/iter-*/*-message.xml`, the role reports
   (`iter-1/surveyor.json` or, for a sliced survey, `iter-1/surveyor-<id>.json`
   and `iter-1/authoring-<id>.md` per slice; `iter-<n>/author-<id>.json` and
   `iter-<n>/author-<id>.md` per author slice, or `iter-<n>/author.json` for a
   single author; `iter-<n>/reviewer-<slice>.md` per reviewer slice and the
   joined `iter-<n>/reviewer.md`), the slice plans
   (`iter-<n>/<role>-slices.json`) and
   `steps/create-requirements/state.json` to see which phases completed.
2. Re-read the `<requirements_dir>` tree against recorded author claims — does
   the actual `<functional_dir>`/`<non_functional_dir>` file set match what the
   recorded author results claim?
3. Check delivery progress: does the delivery branch exist
   (`git branch --list "<branch>"` / `git ls-remote --heads origin "<branch>"`)? Was a
   PR already opened (`gh pr list --head "<branch>" --json number,url`)?
4. Continue from the first unfinished phase. If reviewed docs already pass and the PR
   is open, skip straight to Finish with the recorded references.
5. Pick up at the first missing role: no `iter-1/authoring.md` → survey; a
   DRAFT baseline the ledger does not yet record as confirmed → confirm it
   (Interactive-confirm below); an author result with no review → review it; a
   review with findings and no later author result → author with those
   findings as `<context>`. A resume never re-runs the surveyor once its notes
   exist; the authoring notes (`iter-<n>/authoring.md`) belong to their
   iteration.
6. A sliced phase resumes slice by slice: read its `iter-<n>/<role>-slices.json`
   and re-run ONLY the slices whose own report is missing (a surveyor slice
   without `iter-1/authoring-<id>.md` and `iter-1/surveyor-<id>.json`, an author
   slice without `iter-<n>/author-<id>.json`, a reviewer slice without
   `iter-<n>/reviewer-<id>.md`), all of them in ONE message, then run the join
   (`acs.py notes merge`) over EVERY slice file of the plan. A slice whose
   report exists is never re-run; every join reads only files it never writes,
   so re-running a join is idempotent. When every author slice's report exists
   but `iter-<n>/author-integration.json` does not (and two or more authors
   ran), run the integration pass before the notes join and the review.

If `context.handoff_summary` exists, read it (and
`steps/create-requirements/handoff-context.md` if present), do a light
reconcile of the same checks, and continue from where it points.

## Reflection loop — surveyor → author → review

The loop is surveyor → author → review, max 3 iterations. Iteration 1 runs
the surveyor once: it classifies the mode, enumerates or plans the
elicitation of the feature areas, and writes its authoring notes (the
per-area outline, the open points) read-only. You confirm its DRAFT baseline
with the user, then spawn the author, who writes the area files from the
notes and the confirmation; the reviewer judges the result fresh. On
iterations 2-3 the reviewer's findings go verbatim into the next author
`<task>` `<context>` and the author authors the remediation — the surveyor
never runs again; its notes are the fixed baseline every later iteration is
judged against.

| Role | Kind | Agent | Spawn as |
|------|------|-------|------------|
| surveyor | survey | `acs:create-requirements-surveyor` | `context.agents.surveyor` |
| author | write | `acs:create-requirements-author` | `context.agents.author` |
| reviewer | judge | `acs:create-requirements-reviewer` | `context.agents.reviewer` |

Spawn subagents with the Agent tool: `subagent_type`
`acs:create-requirements-surveyor` / `acs:create-requirements-author` /
`acs:create-requirements-reviewer` (fall back to the un-namespaced name if the runtime
rejects the namespaced one). Spawn each role under the name in `context.agents.<role>` — the plugin's
`acs:create-requirements-<role>`, or the generated `acs-create-requirements-<role>`
copy `acs step start` wrote where `settings.models` sets a model or effort for it.
Model and effort travel with that agent, so pass none of your own. If the runtime
rejects the agent, FAIL the run with that exact error — no silent fallback.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops (`for i in $(seq 1 40); do
sleep 15; done` and its kin), which wait a fixed ten minutes whatever the
agent did and spent a whole 1800s setup on the 2026-09-15 release gate.

**What an iteration counts:** one author -> review round. The survey belongs
to iteration 1 and is not a round of its own.
`/acs:create-requirements` has no path-driven review-depth selection: the
cap is a fixed 3 on every run.

All messages follow `the SubagentStop hook's message check`; the `phase=` of
every task and result is the role (`surveyor`, `author`, `reviewer`). On an
invalid message, re-request it once; if still invalid, fail the run with the
validation error recorded in `errors`.

Every phase output is persisted at the phase boundary, BEFORE the next phase
starts: the SubagentStop hook snapshots each returned message to
`steps/create-requirements/iter-<n>/<role>-message.xml`; if that snapshot is
missing (a host that does not fire the hook), write the `<task>` and
`<result>` there yourself. The roles' own artifacts are the authoring notes
`iter-<n>/authoring.md` (Mode & evidence; Requirement outline; Open
questions; Risks; Reviewer checklist — the surveyor writes iteration 1's, the
author carries them forward), `iter-1/surveyor.json`, `iter-<n>/author.json`
and `iter-<n>/reviewer.md`; every iteration's reviewer `<inputs>` name that
iteration's authoring notes. Decomposition is YOURS alone — subagents never
spawn subagents.

### Fan-out — slices, the join, the cap

Every fan-out in this skill is yours: you spawn N instances of the SAME agent
in ONE message (all foreground, all in the same Agent-tool batch), wait for
ALL of them, and join their outputs before the next phase starts. The rules
every sliced phase follows:

- **Slice id on the wire.** Each parallel instance's `<task>` carries
  `slice="<id>"` (`<task skill="create-requirements" phase="author"
  slice="fn-checkout" …>`) and its `<result>` echoes it, so the SubagentStop
  snapshot lands at `iter-<n>/<role>-<id>-message.xml` with no collision. An
  un-sliced instance omits `slice` exactly as before. A slice id is a short
  lowercase name (`api`, `checkout`, `fn-admin-cli`); the join derives each id
  from the part of the file name after the prefix all its inputs share, so ids
  may carry hyphens. `integration` is reserved for the author integration pass.
- **Slice plan first.** Before spawning, write the partition to
  `steps/create-requirements/iter-<n>/<role>-slices.json` (`{"<id>": [<the
  paths, area files or dimension numbers it owns>], …}`), so a resume knows
  which slices were planned.
- **Per-slice files.** A surveyor slice writes `iter-1/authoring-<id>.md` and
  `iter-1/surveyor-<id>.json`; an author slice writes `iter-<n>/author-<id>.json`
  and its notes contribution `iter-<n>/author-<id>.md`; a reviewer slice writes
  `iter-<n>/reviewer-<id>.md`.
- **The join is deterministic, never prose-merging by you.** One command joins
  the slice files by `## ` heading (first file's preamble; each H2 once, in
  first-seen order; bodies concatenated in input order, each prefixed by a
  `<!-- slice: <id> -->` line) into the ONE file every downstream reader and
  checker reads:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
    --out <partition>/steps/create-requirements/iter-<n>/<joined file> \
    <partition>/steps/create-requirements/iter-<n>/<slice file 1> <…slice file 2> …
  ```

  It prints `{ok, out, sections, inputs}` and refuses when a slice file is
  missing — a missing slice is a failed slice, never a smaller join.
- **Cap.** At most `max_parallel = 4` instances per phase; beyond the cap, run
  the slices in waves of 4 (each wave one message) and join once after the last
  wave.
- **Failure.** A slice that returns `failed` or no usable `<result>` fails its
  phase: re-run the failed slices once (together, in ONE message); still
  failing → fail the run with the error recorded. No phase ever proceeds with
  a missing slice.

### Survey — iteration 1 only

The surveyor's first job is mode classification, keyed on whether
`<requirements_dir>` already holds functional/non-functional content:

- **brownfield** (headline) — the requirements set is absent or sparse AND the
  repo has real code. Plan to reverse-engineer per-area requirements from the
  codebase (architecture-aware feature-area enumeration with a codebase-inventory
  fallback), code-cited and marked DRAFT.
- **amend** — the requirements set is already substantially populated. Plan a
  surgical augmentation: which absent/ungrounded area files gain new content,
  which existing files are preserved byte-for-byte.
- **greenfield** — no meaningful codebase to reverse-engineer AND the set is
  absent, so each elicited area maps to a `<functional_dir>/<feature>.md`
  (behavioral feature) or `<non_functional_dir>/<item>.md` (NFR item) target,
  DRAFT-marked. Plan the elicitation: per candidate feature area, the behavior
  it must have (a functional requirement), and per candidate quality concern,
  the constraint it must meet (a non-functional requirement) — mirroring
  create-prd's greenfield elicitation. Never silently fall through to
  brownfield and never invent a product fact the user has not confirmed.

The surveyor also runs the shared ADR-0012 design-time doc-consistency step;
any findings surface through the "Clarification ledger first" mechanism below
(User interaction). It is read-only on the repo: it records the
classification, the outline and the open points in its authoring notes and
returns `needs_input` with the DRAFT baseline before any area file is written
(see Interactive-confirm below).

**G36 declaration (AC-6).** Every author/review task's `<constraints>` carries:

- `required_sections` — declared **per produced area file**, from the
  confirmed outline in the surveyor's authoring notes. There is no single fixed
  section skeleton across all files (each feature/item file's sections follow
  the existing living-requirements prose format); the surveyor names the
  concrete heading list for each file in its notes, and the coordinator carries
  that list into every author task and the iteration's review task.
- `audience_style_profile` — always `engineers (behavioral-contract prose)`, the
  same constraint-passing mechanism `/acs:create-docs` uses for each doc
  set's own G36 gate.

**Per-file format (finalized).** Both `<functional_dir>/<feature>.md` and
`<non_functional_dir>/<item>.md` open with the `DRAFT — human-confirm-required`
marker line, then follow the existing living-requirements prose format — the
`MUST` / `SHOULD` / `MAY` / `[OPEN]` / `[ASSUMPTION]` vocabulary — with NO fixed
universal heading skeleton (design Decision B-revised). The surveyor names the
concrete `required_sections` heading list per file in its notes' outline; this
subsection documents that as the finalized per-file format rather than an
implicit convention. No new template file is introduced — the
functional/non-functional model itself is the format.

Example survey task (fill real values; `<context>` carries `$ARGUMENTS` and any
clarification answers the ledger already records):

```xml
<task skill="create-requirements" phase="surveyor" ticket-id="SHOP-1" iteration="1">
  <objective>Classify mode (brownfield/greenfield/amend) with evidence; enumerate or plan the elicitation of feature areas; record the per-area outline (with each file's required_sections) and the open points in the authoring notes; write no repo file.</objective>
  <inputs>
    <file>/abs/workspace/acme-shop/SHOP-1/ticket.json</file>
    <file>/abs/repo/docs/requirements/README.md</file>
    <file>/abs/repo/docs/architecture/hld/c4-container.md</file>
  </inputs>
  <constraints>
    <constraint name="requirements_dir">docs/requirements</constraint>
    <constraint name="functional_dir">docs/requirements/functional</constraint>
    <constraint name="non_functional_dir">docs/requirements/non-functional</constraint>
    <constraint name="audience_style_profile">engineers (behavioral-contract prose)</constraint>
  </constraints>
  <context>User focus notes from $ARGUMENTS.</context>
</task>
```

The surveyor returns `needs_input` with its notes in `<outputs>` and the DRAFT
baseline plus the open points in `<questions>`. Confirm them with the user
(Interactive-confirm below), then spawn the author with the answers in
`<context>`.

#### Survey slices — brownfield/amend over disjoint repo areas

Slice the survey when the repo has real code (brownfield or amend) spread over
**two or more disjoint top-level areas** — the containers/components the
architecture doc set names when one exists, else the top-level packages,
services, apps or CLI surfaces of the codebase inventory (the same candidates
the surveyor's feature-area definition enumerates). Greenfield never slices
(there is no code to survey; the elicitation plan is one piece), and a repo
whose code sits in one area runs the single surveyor above.

**Partition rule.** Slice `lead` owns the repo root's files, the docs tree
(the existing `<requirements_dir>` set and the architecture doc set) and the
whole-set sections: `## Mode & evidence` — it classifies the mode, applying
the amend "majority of the enumerated feature areas" test to the full
candidate list you partitioned, which its task carries — and the ADR-0012
doc-consistency step. Every other slice is one area, named by its directory or
container basename (`checkout`, `catalog`, `admin-cli`), and
owns only that area's paths: it enumerates and code-grounds the feature areas
inside them, outlines their `<functional_dir>/<feature>.md` files (with each
file's `required_sections`) and any `<non_functional_dir>/<item>.md` item its
code evidences under `## Requirement outline`, and records its own `[OPEN]`
points, `## Risks` and `## Reviewer checklist` entries. An area is a set of
top-level paths and no path belongs to two slices, so no two slices survey the
same code. An NFR item two slices both evidence appears in the joined outline
under both slice markers; it is still ONE file with ONE author (Author below).

1. Write `iter-1/surveyor-slices.json`, then spawn `lead` plus one surveyor
   per area in ONE message (cap 4, waves beyond it), each `<task
   skill="create-requirements" phase="surveyor" slice="<id>" …>` carrying
   `<constraint name="survey_area"><its top-level paths, or "lead"></constraint>`
   and, for `lead`, `<constraint name="candidate_areas"><every area you
   partitioned></constraint>`, beside the survey constraints above.
2. Join the notes, `lead` first so `## Mode & evidence` opens the file:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
     --out <partition>/steps/create-requirements/iter-1/authoring.md \
     <partition>/steps/create-requirements/iter-1/authoring-lead.md \
     <partition>/steps/create-requirements/iter-1/authoring-<area-1>.md …
   ```

3. Present the DRAFT baseline and the open points of ALL slices to the user in
   ONE grouped clarification-ledger ask (Interactive-confirm below) — never one
   ask per slice.

### Interactive-confirm, between the surveyor and the author

Present the surveyor's DRAFT baseline — which feature areas will be elicited,
extracted, or augmented, and which are `[OPEN]` — and the open points via the
clarify ledger (see User interaction below), batched in one interaction when
≥2 questions are open. An elicited, extracted, or augmented requirement is a
**DRAFT baseline, never authoritative without confirmation**: this
confirmation step MUST complete before the author writes an area file — it
is what the surveyor's `needs_input` round-trip exists for.

**The DRAFT / interactive-confirm discipline applies uniformly to all three
modes.** A requirement — elicited (greenfield), extracted (brownfield), or
augmented (amend) — is a DRAFT baseline the user must review and confirm before
it is authoritative; open points are surfaced for confirmation, and nothing is
written as authoritative without the human gate (C-22).

### Author — the write

Prepare the delivery branch before the first author runs (deterministic plumbing —
you do it, not the author):

```bash
DEFAULT_BRANCH=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)
git fetch origin "$DEFAULT_BRANCH" && git checkout -b "<branch>" "origin/$DEFAULT_BRANCH"
```

`<branch>` renders `settings.formats.branch_name` (default
`{type}/{ticket_id}-{slug}`) with `ticket_id` = delivery ticket id, `type` = `task`,
`slug` = slugified ticket title. On a fresh repo with no remote default branch yet,
`git checkout -b "<branch>"` from the current HEAD instead. If checkout fails
(conflicting local changes), surface the git error and ask the user. Iterations 2-3
stay on the branch.

Spawn the author (`phase="author"`) with the surveyor's notes
(`iter-1/authoring.md`) in `<inputs>`, the confirmed outline's per-file
`required_sections`, the user's answers, and the mode:

```xml
<task skill="create-requirements" phase="author" ticket-id="SHOP-1" iteration="1">
  <objective>Write the confirmed area files from the authoring notes and the user's confirmation.</objective>
  <inputs>
    <file>/abs/workspace/acme-shop/SHOP-1/ticket.json</file>
    <file>/abs/workspace/acme-shop/SHOP-1/steps/create-requirements/iter-1/authoring.md</file>
  </inputs>
  <constraints>
    <constraint name="requirements_dir">docs/requirements</constraint>
    <constraint name="functional_dir">docs/requirements/functional</constraint>
    <constraint name="non_functional_dir">docs/requirements/non-functional</constraint>
    <constraint name="required_sections">functional/checkout.md: MUST/SHOULD/MAY/[OPEN]/[ASSUMPTION]</constraint>
    <constraint name="audience_style_profile">engineers (behavioral-contract prose)</constraint>
    <constraint name="mode">brownfield</constraint>
  </constraints>
  <context>C-1: DRAFT baseline confirmed (checkout, catalog, accounts; performance, security). C-2: admin-cli out of scope.</context>
</task>
```

The author — the only role that mutates the repo — writes, per the mode:

- **brownfield/amend** — one `<functional_dir>/<feature>.md`
  per behavioral feature and one `<non_functional_dir>/<item>.md`
  per NFR item, classifying each requirement functional-vs-non-functional before
  writing it. Augment-only-absent: an existing area file is preserved byte-for-byte,
  never overwritten.
- **greenfield** — writes one
  `<functional_dir>/<feature>.md` per elicited behavioral
  feature and one `<non_functional_dir>/<item>.md` per
  elicited NFR item, from the survey's elicitation outline plus the user's
  answers; DRAFT-marked. No code-citation is required or expected (there is no
  code to cite) — every clause is grounded in the user's elicited answer, cited
  as such.

Should the author return `needs_input` (a fact the confirmation does not
settle), ask the user and re-run the author for the same iteration with the
answer in `<context>`.

**Synthesis of a sliced survey.** When the survey ran sliced, the joined
`iter-1/authoring.md` is a mechanical join, not a synthesis: the author(s)
reading it MUST reconcile it. Where two slices' notes contradict each other (a
feature area claimed by two slices with different scope, an NFR item evidenced
differently, a term defined two ways), the author records the resolution with
the evidence that settles it under a `## Synthesis` heading of its own notes,
or returns `needs_input` with the contradiction as a question — never silently
picks one side. A single author keeps `## Synthesis` in `iter-1/authoring.md`;
a sliced author keeps it in `iter-1/author-<id>.md` for the contradictions that
touch its own file, and the integration pass (below) checks that every slice
used the same reconciled facts.

#### Author slices — one author per area file, the default from iteration 1

The deliverable splits into disjoint files, so the write runs sliced from
iteration 1 whenever the confirmed outline names two or more area files; an
outline with a single area file runs one un-sliced author exactly as the task
example above shows (it also writes the README decision-log row itself, and no
integration pass runs).

**Partition rule.** A slice owns exactly one area file of the confirmed
outline — a `<functional_dir>/<feature>.md` or a `<non_functional_dir>/<item>.md`
— together with that file's `.evidence.md` sidecar, and nothing else. The
slice id is `fn-<basename>` for a functional file and `nfr-<basename>` for a
non-functional one (`fn-checkout`, `nfr-performance`), so no two ids collide
and none is `integration`. Each slice's task carries `<constraint
name="files">` listing exactly the repo paths it may create or change, derived
from the joined outline; every path is listed in exactly one slice's `files`,
and an author never writes outside its own list — so no two slices can touch
the same file. The run-level files that list or link the slices' outputs
belong to no slice: they are the integration pass's.

1. Write `iter-<n>/author-slices.json`, then spawn one author per slice in ONE
   message (cap 4; beyond it, waves of 4, each wave one message), each
   `<task skill="create-requirements" phase="author" slice="<id>" …>` carrying
   its `files`, the `required_sections` of its own file, and the same inputs,
   mode and `<context>` as the task example above.
2. A sliced author never edits the shared notes: it writes its notes
   contribution — only `## Deviations`, `## Synthesis` and, on iteration 2+,
   `## Findings addressed` — to `iter-<n>/author-<id>.md`, and its report to
   `iter-<n>/author-<id>.json`.
3. **Integration pass — after ALL slices finish, BEFORE the reviewer.** Spawn
   ONE more author with `slice="integration"` (the pattern code-complex's
   final integration implementer uses). Its task names every slice's area
   files, `author-<id>.md` notes and `author-<id>.json` reports in `<inputs>`,
   and `<constraint name="seams">` lists the seams it owns — it reconciles
   ONLY these, never a slice's substance:
   - the **shared glossary** — a term, actor or identifier the slices' files
     define or use must be defined once and used the same way everywhere (the
     set's glossary file, when it keeps one, and the terms in the area files);
   - the **NFR cross-references** — the tie-break's one-line cross-reference
     from a non-functional file to its paired functional file, and every link
     between functional and non-functional files, resolve both ways;
   - the **requirements README index** — `<requirements_dir>/README.md`: the
     ONE decision-log row for this run and any index that lists the area
     files;
   - duplicated or contradicting clauses across area files, and each slice's
     use of the reconciled survey facts (`## Synthesis`);
   - any ADR-0012 doc-consistency adjustment outside the area files.

   It writes its notes contribution (`## Seams reconciled`) to
   `iter-<n>/author-integration.md` and `iter-<n>/author-integration.json`
   listing each seam it changed (file, what, why, which slices). A genuine
   conflict it cannot resolve from the evidence comes back as
   `status="needs_input"` with a question: ask the user, then re-run the
   integration pass with the answer. The pass is skipped when only one author
   ran.
4. Join the notes deterministically, the integration contribution last. On
   iteration 1, first freeze the survey's notes once — `cp -n
   iter-1/authoring.md iter-1/survey-baseline.md` — so the join never reads its
   own output:

   ```bash
   # iteration 1
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
     --out <partition>/steps/create-requirements/iter-1/authoring.md \
     <partition>/steps/create-requirements/iter-1/survey-baseline.md \
     <partition>/steps/create-requirements/iter-1/author-<id-1>.md … \
     <partition>/steps/create-requirements/iter-1/author-integration.md
   # iteration n >= 2 — the previous iteration's notes carried forward
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
     --out <partition>/steps/create-requirements/iter-<n>/authoring.md \
     <partition>/steps/create-requirements/iter-<n-1>/authoring.md \
     <partition>/steps/create-requirements/iter-<n>/author-<id-1>.md … \
     <partition>/steps/create-requirements/iter-<n>/author-integration.md
   ```

   Leave out `author-integration.md` on an iteration the pass did not run.

5. Authors never `git add` or commit; your single commit after the review
   passes (Deliver) is the only git write, so no `index.lock` contention
   arises. Should that commit ever hit a held `index.lock`, wait briefly and
   retry the commit — never force anything, never delete the lock.

The reviewer always runs after every author slice and the integration pass
have finished, and judges the integrated result; a seam inconsistency is a
finding like any other. On iterations 2-3 the reviewer's findings go verbatim
into the author `<task>`'s `<context>`; the surveyor does not re-run. Every
sliced author gets ALL findings verbatim, and re-runs only when a finding names
a file in its `files`; a seam finding (glossary, cross-reference, README index,
a contradiction between two slices' files) goes to that iteration's integration
pass; a finding that names no slice's file and no seam (an uncovered area) is
assigned by you to exactly one slice — a new slice for a new area file. Slices
with no finding to fix do not re-run, and their files stand. The integration
pass runs on every iteration in which two or more authors ran or a seam
finding is open.

### Review

Spawn the reviewer (`phase="reviewer"`) with ONLY artifact references (the produced
files, the iteration's authoring notes, the ticket, the git diff) — never the
author's reasoning. Its `<constraints>` also carry `required_sections` (per
produced area file) and `audience_style_profile` (both declared above in the G36
declaration and the author task example). It
re-reads everything fresh and checks, all findings blocking — including
`audience-style` (an unwaived audience-mismatch blocks; a coordinator-recorded
ledger waiver via `clarify.py --source assumption` makes it `severity="info"`,
non-blocking):

- every planned area file exists, is non-empty, and follows its declared
  `required_sections` (the deterministic **structure** dimension,
  `structure_lint.py --sections "<required_sections>" --ordered <file>` run per
  produced area file);
- mode conformance — the produced set matches the classified mode (greenfield
  elicited files, or brownfield/amend augmentation);
- authoring conformance — the produced files realize the confirmed outline in
  the authoring notes;
- amend mode: `git diff` shows only the intended new/augmented area files —
  every existing area file is byte-identical;
- iteration 2+: every prior finding from `<context>` is actually fixed.

**Reviewer slices — every iteration, the default.** The reviewer has thirteen
check dimensions (numbered in `create-requirements-reviewer.md`), so it always
runs as three slices, each a fresh instance of `acs:create-requirements-reviewer`
whose task carries `slice="<id>"` and `<constraint name="dimensions">` naming
the dimension numbers it owns, beside every input and constraint above:

| Slice | Dimensions | Owns the run of |
|---|---|---|
| `floor` | 1 required-file-presence, 7 DRAFT marker, 10 augment-only-absent / no-overwrite, 12 structure | the deterministic floor: `structure_lint.py` per produced area file and `git diff -- <requirements_dir>` — each run in this slice only, once per iteration |
| `evidence` | 5 coverage, 6 citation, 8 no-fabrication, 9 functional/non-functional routing spot-check | the independent feature-area re-enumeration and the body-anchor → `.evidence.md` sidecar joins |
| `conformance` | 2 mode-conformance, 3 authoring-conformance, 4 iteration 2+ regression check, 11 interactive-confirm discipline, 13 audience-style | `clarify.py list` and the judgement against the authoring notes |

Grounding policing applies in every slice. Write `iter-<n>/reviewer-slices.json`,
spawn the three slices in ONE message and wait for all three. Then
**de-duplicate**: the slices own disjoint dimensions, so the join below is the
synthesis, but two slices can still report one defect (a missing section seen
by two dimensions). Drop a finding that cites the same location and the same
defect as another slice's finding, keeping the one with the higher severity,
and record every drop — which finding, from which slice, kept in favour of
which — under `## De-duplicated findings` in `iter-<n>/reviewer-dedup.md`
(write `none` there when nothing was dropped). Join the slices' reports, in the
table's order, with the de-duplication record last, into the one report every
later reader reads:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
  --out <partition>/steps/create-requirements/iter-<n>/reviewer.md \
  <partition>/steps/create-requirements/iter-<n>/reviewer-floor.md \
  <partition>/steps/create-requirements/iter-<n>/reviewer-evidence.md \
  <partition>/steps/create-requirements/iter-<n>/reviewer-conformance.md \
  <partition>/steps/create-requirements/iter-<n>/reviewer-dedup.md
```

**Pass rule for sliced reviewers:** the iteration passes only if EVERY slice
returned `status="completed"` with zero blocking findings. Any slice's blocking
finding blocks the iteration. A slice that failed or returned no usable result
fails the iteration — never "pass with a missing slice".

Zero findings across all slices = pass -> Deliver. The findings that go on
are the de-duplicated set. Findings -> feed every
slice's findings verbatim into the next iteration's author `<task>` `<context>`
— the surveyor does not re-run — and re-run author -> review. After iteration 3 with findings remaining: STOP —
final status `failed`, findings recorded; go to Finish (no PR is opened).

## Deliver the docs-only PR

Only after the reviewer passes:

```bash
git add "<functional_dir>" "<non_functional_dir>"
git add "<requirements_dir>/README.md" 2>/dev/null || true   # the decision-log row / index, when the set has a README
git commit -m "<rendered formats.commit_message>"      # default {ticket_id} {summary}
git push -u origin "<branch>"
gh label create ACS 2>/dev/null || true                # create the label if missing
```

- PR title renders via the helper — NOT LLM prose composition — capturing its
  stdout as `<rendered title>`:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pr-conventions.py" render-title \
    --template "<settings.formats.pr_title>" --ticket-id <ticket_id> --type <ticket.type> \
    --title "<delivery ticket's title>" --summary "<summary>" --external-key "<ticket.external.key or empty>" \
    --provider "<ticket.external.provider or empty>"
  ```

- PR body: resolve `settings.formats.pr_description_template` (default
  `pr-default` -> `${CLAUDE_PLUGIN_ROOT}/templates/pr-default.md`; a custom name ->
  `<repo>/.acs/templates/<name>.md`; else an absolute path). Fill `{ticket_id}`,
  `{type}`, `{title}`, `{summary}`, `{external_key}` from `ticket.json` and this
  run's state — never from conversation memory. Changes = the area files added or
  amended; Test plan = the review dimensions checked; mark TDD/coverage checklist
  items `N/A (docs-only PR)`. Write the filled body to
  `steps/create-requirements/pr-body.md` before the self-check below.
- **Pre-open self-check** — before `gh pr create`, self-check the filled
  body with the helper's `check` subcommand (a deterministic CLI call, never
  a spawned subagent). It checks exactly what CI will — that the body names
  its ticket (ADR-0106) — plus two hygiene scans, for an unrendered
  `{placeholder}` and a leftover `<!-- -->` comment:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pr-conventions.py" check \
    --body-file "steps/create-requirements/pr-body.md" --ticket-prefix <settings.ticket_prefix>
  ```

  On pass, proceed to `gh pr create` unchanged. On failure, this check
  blocks/retries: apply a bounded local re-fill/re-check (up to 2
  attempts) rather than opening a non-conforming PR; if still failing after
  the bounded retries, STOP — do not call `gh pr create` — surface the
  blocking finding with the failing heading(s)/detail(s) in the result
  document.

```bash
gh pr create --base "$DEFAULT_BRANCH" --head "<branch>" \
  --title "<rendered title>" \
  --body-file "steps/create-requirements/pr-body.md" \
  --label ACS
gh pr view "<branch>" --json number,url
```

- Record the PR number, URL, and branch for the result document.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list --ticket <ticket-id>`
and reuse any recorded answer — re-asking an answered question is a defect.
When ≥2 clarifications are open, present them to the user in ONE grouped
interaction (e.g. a single AskUserQuestion containing all open questions as a
numbered list), not serial round-trips — one interaction per question wastes
user time. The DRAFT baseline and open points of ALL surveyor slices are one
batch: wait for every slice, then ask them in that ONE grouped interaction (a
question two slices raise word for word is asked once). Record each answer as its own `clarify.py add` entry (one `C-<n>`
per question, `--source` preserved). Never skip a question, merge two questions
into one entry, or auto-answer a question outside the existing
`--source assumption --rationale "..."` rule.
Record every Q&A — obtained interactively or relayed in a /ship brief — with
`clarify.py add --skill create-requirements --question "..." --answer "..." --ticket <ticket-id>`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`. If the user is unavailable or says "you decide": record the
decision with `--source assumption --rationale "..."` — assumptions surface
in the completion report's Findings and the PR body until a user confirms.
Before a needs_input handoff, record the outgoing questions as `open`
(`clarify.py add` without `--answer`).

- **Brownfield**: present the reverse-engineered baseline (DRAFT, code-cited,
  human-confirm-required) and ask ONLY the open points the surveyor flagged — an
  extracted requirement is never authoritative without confirmation.
- **Amend**: confirm exactly which absent/ungrounded area files are augmented and
  why before the author writes; every other area file is untouched.
- **Greenfield**: elicit the definition from the user and map it to
  `<functional_dir>/<feature>.md` files (the feature list — what the
  product/system does) and `<non_functional_dir>/<item>.md` files (the NFR
  list — performance/security/reliability/portability/operability constraints).
  Batch questions (AskUserQuestion or plain questions) via the same
  clarify-ledger-first mechanism used for brownfield/amend; when `$ARGUMENTS`
  already carries notes, propose drafts to confirm instead of interrogating
  from zero.
- Ask only when genuinely ambiguous; never invent product facts. If you
  genuinely cannot reach the user (e.g. a non-interactive run), return a
  `<handoff skill="create-requirements" ticket-id="<id>" status="needs_input">` with
  `<questions>` instead of guessing.

## Context pressure

If your context is running low mid-run: flush in-flight work and soft context (user
answers, decisions, partial findings, gotchas) to
`steps/create-requirements/handoff-context.md`, then run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --ticket <ticket-id> --summary "<done / in-flight / next / decisions>"
```

and tell the user the printed `continue_with` command. Never burn the last of the
context on work that would be lost.

## Finish

MANDATORY final step — never skipped, also on failure.

1. Write `steps/create-requirements/result.json` per the result-document
   contract (INTERNALS.md), with the canonical `states` keys for create-requirements —
   `requirements` and `pr`, exact names:

   ```json
   {
     "status": "completed",
     "summary": "Requirements doc set produced/amended and docs-only PR opened",
     "states": {
       "requirements": {"path": "docs/requirements", "files": ["docs/requirements/functional/checkout.md"]},
       "pr": {"number": 12, "url": "https://github.com/acme/shop/pull/12", "branch": "task/MAR-51-product-requirements-doc-set"}
     },
     "findings": [],
     "errors": []
   }
   ```

   On failure keep whatever is true: status `failed`, remaining reviewer findings in
   `findings`, `states.requirements` if any files were written, NO `states.pr` if no
   PR was opened, and the reason in `summary`.

2. Run the post-hook:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-requirements.py" --result-file "<the result.json you just wrote>"
   ```

   It finalizes the run entry, updates `run.json` / `tickets-index.json`,
   flips the delivery ticket to `in_review` (PR recorded), and releases the
   `.lock`.

3. Report a compact summary to the user: delivery ticket id, mode
   (greenfield/brownfield/amend), files written, PR URL — and tell them to
   review the PR themselves, then run `/acs:merge-pr <delivery-ticket-id>` to land it.
   Under /acs:ship, return ONLY the `<handoff>` XML as your final message: status,
   summary <=1KB, artifact refs, next-step.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty; under /acs:ship your final message is the `<handoff>` XML instead — this report is for direct invocations:

```markdown
## /acs:create-requirements · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: requirements area files written/amended under `<requirements_dir>`; delivery ticket id; PR number/URL
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <partition files, repo paths, branch, PR URL>
- **Metrics**: iterations <n>/<cap> · <wall time>
- **Next**: `/acs:merge-pr <ticket-id>` after reviewing the docs PR
```
