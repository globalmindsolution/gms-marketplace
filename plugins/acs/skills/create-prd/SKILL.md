---
name: create-prd
description: Define or amend the product PRD — vision, problem, personas, goals with measurable success metrics, prioritized features, NFRs, constraints — plus a roadmap, shipped as a docs-only PR on its own delivery ticket. Use when starting a product, onboarding acs onto an existing codebase, or when scope changes require a PRD amendment. Use for any request to write down what a product is, its problem, users and success metrics, or to amend its scope, priorities or roadmap — including when leadership cuts or reprioritizes a feature the existing PRD still lists. Invoke it directly on such a request — it confirms scope and gathers what it needs from the user itself, so there is nothing to ask before running it.
argument-hint: "[product notes | delivery-ticket-id to resume]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-prd. You produce or amend the PRD doc set
(`prd.md` + `roadmap.md`) in the consumer repo — wherever the repo already keeps
its PRD, else at `docs/product/` — under a fresh **delivery ticket**, and you ship
it yourself as a docs-only PR — `/acs:code` and `/acs:create-pr` are NOT involved.
You orchestrate three subagents — surveyor → author → review: a read-only
surveyor establishes the mode, the outline and the open questions, you put the
questions to the user, an author writes the documents from the notes and the
answers, and a reviewer judges them fresh. You never write the PRD content
yourself. Two of the three phases fan out: the survey runs as parallel
surveyor slices over disjoint areas of the repo when a brownfield or amend
code survey spans two or more of them, and the review always runs as three
parallel reviewer slices over disjoint check dimensions. The author never
splits — `prd.md` and `roadmap.md` are one coupled deliverable (see Author).

## Start

MANDATORY first action. Pick the form by inspecting `$ARGUMENTS`:

- `$ARGUMENTS` contains a ticket id matching the repo prefix (e.g. `SHOP-1` — you are
  resuming an interrupted or handed-off delivery ticket):

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-prd --ticket <ticket-id>
  ```

- Otherwise (fresh PRD or amendment — every run gets a NEW delivery ticket):

  Before calling `acs step start --allocate`, detect whether this is an **amend** run
  by locating the repo's PRD the way any session finds a document: CLAUDE.md and
  whatever docs index it or the repo points at (e.g. `docs/README.md`), then a
  Glob/Grep for `prd.md` or a PRD by content. Found → amend; that file is `<prd>` and
  its roadmap (located the same way, else `roadmap.md` beside it) is `<roadmap>`. Not
  found → `<prd>` = `docs/product/prd.md`, `<roadmap>` = `docs/product/roadmap.md`,
  the conventional default. This mirrors the surveyor's amend definition (see
  Survey below).

  - **Amend mode with a usable `$ARGUMENTS` request**: pass a `--title` flag:

    ```bash
    python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-prd --allocate \
      --title "Amend PRD: <≤~10-word summary of what changed>"
    ```

    A usable `$ARGUMENTS` request (clarification C-2): after stripping any leading
    delivery-ticket id (a token matching the repo prefix pattern, e.g. `MAR-51`),
    `$ARGUMENTS` contains free text describing what the amendment changes from which a
    short (about 10 words or fewer) summary can be formed. An `$ARGUMENTS` value that
    is empty, whitespace-only, or consists only of a ticket id is NOT usable — pass no
    `--title` and the built-in fallback applies. This is coordinator judgment, not
    parsing machinery; keep the free text of `$ARGUMENTS` as surveyor and author
    input (see below).

    The `--title` value MUST be prefixed `"Amend PRD: "` and MUST name what the
    amendment changes in at most ~10 words total (prefix included), derived from the
    free text of `$ARGUMENTS`. Example:
    `--title "Amend PRD: add org-level enforcement policy"`

  - **All other cases** (greenfield/brownfield — no PRD found — or an
    amendment where `$ARGUMENTS` carries no usable request): pass no `--title`:

    ```bash
    python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-prd --allocate
    ```

  `--allocate` creates the delivery ticket (type `task`, built-in title
  `"Product definition (PRD)"` unless overridden by `--title`), its workspace
  partition, the `.lock`, the session pointer, and the `in_progress` run entry.

If `acs step start` exits non-zero: STOP and surface its stderr verbatim.

Parse the printed context JSON. Key fields: `partition`, `ticket_id`, `ticket`,
`settings` (`formats`, `ticket_prefix`), `models` (per-tier model/effort),
`reconcile`, `handoff_summary`, `design`, `pipeline`, `post_hook`.

Keep the free text of `$ARGUMENTS` (product notes, amendment request): it is
surveyor and author input. `<prd>` and `<roadmap>` are the repo-relative paths
every later section uses; on the resume form, locate them the same way right
after `acs step start`.

## Resume & reconcile

If `context.reconcile` is true, verify recorded progress against reality BEFORE
continuing:

1. Re-read `steps/create-prd/iter-*/*-message.xml`, the role reports
   (`iter-1/surveyor.json` or, for a sliced survey, `iter-1/surveyor-<id>.json`
   and `iter-1/authoring-<id>.md` per slice; `iter-<n>/author.json`;
   `iter-<n>/reviewer-<slice>.md` per reviewer slice and the joined
   `iter-<n>/reviewer.md`), the slice plans (`iter-<n>/<role>-slices.json`) and
   `steps/create-prd/state.json` to see which phases completed.
2. Re-read `<repo>/<prd>` and `<repo>/<roadmap>` — does their content
   match what the recorded author results claim?
3. Check delivery progress: does the delivery branch exist
   (`git branch --list "<branch>"` / `git ls-remote --heads origin "<branch>"`)? Was a
   PR already opened (`gh pr list --head "<branch>" --json number,url`)?
4. Continue from the first unfinished phase. If reviewed docs already pass and the PR
   is open, skip straight to Finish with the recorded references.
5. Pick up at the first missing role: no `iter-1/authoring.md` → survey; a
   survey whose open questions the ledger does not yet answer → ask them (User
   interaction); an author result with no review → review it; a review with
   findings and no later author result → author with those findings as
   `<context>`. A resume never re-runs the surveyor once its notes exist; the
   authoring notes (`iter-<n>/authoring.md`) belong to their iteration.
6. A sliced phase resumes slice by slice: read its `iter-<n>/<role>-slices.json`
   and re-run ONLY the slices whose own report is missing (a surveyor slice
   without `iter-1/authoring-<id>.md` and `iter-1/surveyor-<id>.json`, a
   reviewer slice without `iter-<n>/reviewer-<id>.md`), all of them in ONE
   message, then run the join (`acs.py notes merge`) over EVERY slice file of
   the plan. A slice whose report exists is never re-run; re-joining slice
   files that are all present is idempotent.

If `context.handoff_summary` exists, read it (and
`steps/create-prd/handoff-context.md` if present), do a light reconcile
of the same checks, and continue from where it points.

## Reflection loop — surveyor → author → review

The loop is surveyor → author → review, max 3 iterations. Iteration 1 runs
the surveyor once: it classifies the mode, surveys the codebase or plans the
elicitation, and writes the authoring notes (the outline, the open questions,
the three corroboration sections the reviewer's floor parses) read-only. You
relay its open questions to the user, then spawn the author, who writes
`prd.md` and `roadmap.md` from the notes and the answers; the reviewer judges
the result fresh. On iterations 2-3 the reviewer's findings go verbatim into
the next author `<task>` `<context>` and the author authors the remediation —
the surveyor never runs again; its notes are the fixed baseline every later
iteration is judged against.

**What an iteration counts:** one author -> review round. The survey belongs
to iteration 1 and is not a round of its own. `/acs:create-prd` has no
path-driven review-depth selection: the cap is a fixed 3 in every lane, and
this ticket introduces none.

| Role | Kind | Agent | Model tier |
|------|------|-------|------------|
| surveyor | survey | `acs:create-prd-surveyor` | `context.models.planner` |
| author | write | `acs:create-prd-author` | `context.models.executor` |
| reviewer | judge | `acs:create-prd-reviewer` | `context.models.verifier` |

Spawn subagents with the Agent tool: `subagent_type`
`acs:create-prd-surveyor` / `acs:create-prd-author` /
`acs:create-prd-reviewer` (fall back to the un-namespaced name if the runtime rejects
the namespaced one). Apply the role's tier — `context.models.planner.model` /
`.effort` for the surveyor, `context.models.executor.*` for the author,
`context.models.verifier.*` for the reviewer — at spawn when not
`"inherit"`; if the runtime rejects the model/effort, FAIL the run with that error —
no silent fallback.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops (`for i in $(seq 1 40); do
sleep 15; done` and its kin), which wait a fixed ten minutes whatever the
agent did and spent a whole 1800s setup on the 2026-09-15 release gate.

All messages follow `the SubagentStop hook's message check`; the `phase=` of
every task and result is the role (`surveyor`, `author`, `reviewer`). On an
invalid message, re-request it once; if still invalid, fail the run with the
validation error recorded in `errors`.

Every phase output is persisted at the phase boundary, BEFORE the next phase
starts: the SubagentStop hook snapshots each returned message to
`steps/create-prd/iter-<n>/<role>-message.xml`; if that snapshot is missing (a
host that does not fire the hook), write the `<task>` and `<result>` there
yourself. The roles' own artifacts are the authoring notes
`iter-<n>/authoring.md` (Mode & evidence; PRD outline; Roadmap outline; Code
evidence; Answer fidelity; Roadmap milestones; Open questions; Risks; Reviewer
checklist — the surveyor writes iteration 1's, the author completes them and
carries them forward), `iter-1/surveyor.json`, `iter-<n>/author.json` and
`iter-<n>/reviewer.md`; every iteration's reviewer `<inputs>` name that
iteration's authoring notes. Decomposition is YOURS alone — subagents never
spawn subagents.

### Fan-out — slices, the join, the cap

Every fan-out in this skill is yours: you spawn N instances of the SAME agent
in ONE message (all foreground, all in the same Agent-tool batch), wait for
ALL of them, and join their outputs before the next phase starts. The rules
every sliced phase follows:

- **Slice id on the wire.** Each parallel instance's `<task>` carries
  `slice="<id>"` (`<task skill="create-prd" phase="reviewer" slice="floor" …>`)
  and its `<result>` echoes it, so the SubagentStop snapshot lands at
  `iter-<n>/<role>-<id>-message.xml` with no collision. An un-sliced instance
  omits `slice` exactly as before. A slice id is a short lowercase name
  (`api`, `web-app`, `floor`); the join derives each id from the part of the
  file name after the prefix all its inputs share, so ids may carry hyphens.
- **Slice plan first.** Before spawning, write the partition to
  `steps/create-prd/iter-<n>/<role>-slices.json` (`{"<id>": [<the paths or
  dimension numbers it owns>], …}`), so a resume knows which slices were
  planned.
- **Per-slice files.** A surveyor slice writes `iter-1/authoring-<id>.md` and
  `iter-1/surveyor-<id>.json`; a reviewer slice writes `iter-<n>/reviewer-<id>.md`.
- **The join is deterministic, never prose-merging by you.** One command joins
  the slice files by `## ` heading (first file's preamble; each H2 once, in
  first-seen order; bodies concatenated in input order, each prefixed by a
  `<!-- slice: <id> -->` line) into the ONE file every downstream reader and
  checker reads:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
    --out <partition>/steps/create-prd/iter-<n>/<joined file> \
    <partition>/steps/create-prd/iter-<n>/<slice file 1> <…slice file 2> …
  ```

  It prints `{ok, out, sections, inputs}` and refuses when a slice file is
  missing — a missing slice is a failed slice, never a smaller join.
- **Cap.** At most `max_parallel = 4` instances per phase; beyond the cap, run
  the slices in waves of 4 (each wave one message) and join once after the last
  wave.

### Survey — iteration 1 only

The surveyor's first job is mode classification:

- **amend** — `<repo>/<prd>` already exists. Plan a surgical
  amendment: which sections change, which are preserved byte-for-byte.
- **brownfield** — no `prd.md`, but the repo contains real code. Plan to
  reverse-engineer a baseline PRD from the codebase and existing docs, listing the
  open points that need user confirmation.
- **greenfield** — empty/near-empty repo. Plan the elicitation: what to ask the user
  for vision, problem, personas, goals (+ measurable success metrics), prioritized
  features (MoSCoW), product NFRs, constraints, out-of-scope.

The surveyor also runs the shared ADR-0012 design-time doc-consistency step;
any findings surface through the "Clarification ledger first" mechanism below
(User interaction). It is read-only on the repo: it records the
classification, the outline, the open questions and the three corroboration
sections in its authoring notes and returns `needs_input` with the open
questions before any file is written.

Example task (fill real values; `<context>` carries `$ARGUMENTS` and any
clarification answers the ledger already records):

```xml
<task skill="create-prd" phase="surveyor" ticket-id="SHOP-1" iteration="1">
  <objective>Classify mode (greenfield/brownfield/amend) with evidence; record the prd.md and roadmap.md outline, the elicitation or reverse-engineering survey, the open questions for the user, and the `## Code evidence` / `## Answer fidelity` / `## Roadmap milestones` corroboration sections the reviewer's deterministic floor parses in the authoring notes; write no repo file.</objective>
  <inputs>
    <file>/abs/workspace/acme-shop/SHOP-1/ticket.json</file>
    <file>/abs/repo/docs/product/prd.md</file>
    <file>/abs/repo/README.md</file>
  </inputs>
  <constraints>
    <constraint name="prd">docs/product/prd.md</constraint>
    <constraint name="roadmap">docs/product/roadmap.md</constraint>
    <constraint name="required_sections">Vision; Problem statement; Target users &amp; personas; Goals &amp; success metrics; Features (prioritized); Non-functional requirements; Constraints &amp; assumptions; Out of scope</constraint>
    <constraint name="audience_style_profile">product/business (plainer prose)</constraint>
    <constraint name="amend_rule">amendments preserve untouched sections exactly</constraint>
  </constraints>
  <context>User notes from $ARGUMENTS; any recorded clarification answers.</context>
</task>
```

The surveyor returns `needs_input` with its notes in `<outputs>` and the open
points in `<questions>` (or `completed` when nothing is open). Resolve those
questions with the user (see User interaction): record each through the
clarification ledger, then spawn the author with the answers in `<context>`.
When the survey leaves nothing open, still confirm the scope with the user
before the author runs (the mode rules in User interaction say what to
confirm).

#### Survey slices — brownfield/amend over disjoint repo areas

Slice the survey when the mode is brownfield or amend (you already know which
from Start: a located PRD means amend) AND the code the survey must cite spans
**two or more disjoint top-level areas** of the repo — top-level packages,
services, apps or plugins: the containers the architecture doc set names when
one exists, else the top-level directories of `git ls-files` that hold code.
Greenfield never slices (there is no code to survey; the elicitation plan is
one piece), and a repo whose code sits in one area runs the single surveyor
above.

**Partition rule.** Slice `lead` owns the repo root's files, the docs tree
(including an existing `<prd>` and `<roadmap>`) and the whole-product sections
of the notes: `## Mode & evidence`, the product-level `## PRD outline` (Vision,
Problem statement, personas, goals with their candidate metrics),
`## Roadmap outline`, `## Roadmap milestones` and `## Answer fidelity` — so each
ledger id gets its one line from one slice — plus the ADR-0012
doc-consistency step. Every other slice is one code area, named by its
directory basename (`api`, `web-app`, `billing`), and owns only
that area's paths: it records the features, product NFRs and code evidence its
area proves under `## PRD outline` and `## Code evidence`, candidate milestones
under `## Roadmap outline` (never `## Roadmap milestones`), and its area's
`## Open questions`, `## Risks` and `## Reviewer checklist` entries. An area is
a set of top-level directories and no directory belongs to two slices, so no
two slices survey — or cite — the same path.

1. Write `iter-1/surveyor-slices.json`, then spawn `lead` plus one surveyor
   per area in ONE message (cap 4, waves beyond it), each `<task
   skill="create-prd" phase="surveyor" slice="<id>" …>` carrying
   `<constraint name="survey_area"><its top-level paths, or "lead"></constraint>`
   beside the survey constraints above.
2. Join the notes, `lead` first so the whole-product headings open the file:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
     --out <partition>/steps/create-prd/iter-1/authoring.md \
     <partition>/steps/create-prd/iter-1/authoring-lead.md \
     <partition>/steps/create-prd/iter-1/authoring-<area-1>.md …
   ```

3. Put the open questions of ALL slices to the user in ONE grouped
   clarification-ledger ask (User interaction) — never one ask per slice.
4. The author then runs exactly as below from the joined `iter-1/authoring.md`
   — and **synthesizes** it, because a mechanical join is not a synthesis:
   where two slices' notes contradict each other (one feature described two
   ways, an area's code evidence against a `lead` goal or constraint, a
   candidate milestone that fits no `lead` outline), it records the resolution
   with the evidence that settles it under a `## Synthesis` heading of
   `iter-1/authoring.md`, or returns `needs_input` with the contradiction as a
   question — never silently picks one side. It also reconciles
   `## Roadmap milestones` with the milestone headings it actually writes. No
   integration pass follows: there is one author, so there are no writer
   seams to reconcile.

A slice that returns `failed` or no usable `<result>` fails the survey: re-run
the failed slices once (together, in ONE message); still failing → fail the
run with the error recorded. The join never runs over a missing slice.

### Author — the write

Prepare the delivery branch before the first author runs (deterministic plumbing —
you do it, not the author):

```bash
DEFAULT_BRANCH=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)
git fetch origin "$DEFAULT_BRANCH" && git checkout -b "<branch>" "origin/$DEFAULT_BRANCH"
```

`<branch>` renders `settings.formats.branch_name` (default
`{type}/{ticket_id}-{slug}`) with `ticket_id` = delivery ticket id, `type` = `task`,
`slug` = slugified ticket title — e.g. `task/MAR-51-amend-prd-add-org-enforcement-policy`. On a
fresh repo with no remote default branch yet, `git checkout -b "<branch>"` from the
current HEAD instead. If checkout fails (conflicting local changes), surface the git
error and ask the user. Iterations 2-3 stay on the branch.

Spawn the author (`phase="author"`) with the surveyor's notes
(`iter-1/authoring.md`) and `<partition>/clarifications.json` in `<inputs>`, the
same constraints as the survey plus the classified mode, and the user's answers
(and, on iterations 2-3, the reviewer's findings) in `<context>`. The author —
the only role that mutates the repo — writes:

- `<prd>` with EXACTLY these sections: **Vision**,
  **Problem statement**, **Target users & personas**, **Goals & success metrics**,
  **Features (prioritized)** (MoSCoW: Must/Should/Could/Won't, each feature traced to
  the goal(s) it serves), **Non-functional requirements**,
  **Constraints & assumptions**, **Out of scope**.
- `<roadmap>` — milestones/phases mapped to intended epics, each
  milestone listing the PRD features it delivers.
  - Additionally, maintain a **"Release versions"** mapping table in
    `roadmap.md`: one row per release version, mapping it to the
    milestone(s)/wave it is the version-home of and the epic(s) it delivers.
    This is additive to today's version-labelled milestone prose (e.g. "Wave 3
    — v0.4.2") — no existing milestone/version label is removed or renamed.
    `/acs:release`/`release_notes.py` never reads this table for
    ticket→version resolution (it resolves via the merged-ticket
    archive/`git log` instead) — the table exists purely for roadmap
    readability and the coverage check below, and a gap in it can never break
    a release cut.
- In amend mode: edit `prd.md` in place, preserving untouched sections exactly
  (verify with `git diff -- "<prd>" "<roadmap>"`); update `roadmap.md` only where the
  amendment changes it.

It also completes the notes' `## Answer fidelity` anchors against the text it
wrote. Should the author return `needs_input` (a product fact the answers do not
settle), ask the user and re-run the author for the same iteration with the
answer in `<context>`.

**One author, never sliced — on every iteration.** The two files look
disjoint but are one coupled deliverable, so there is no partition two writers
could own without overlapping: `roadmap.md` derives from `prd.md` (every
milestone lists PRD features, every Must-have must land in a milestone, and a
feature renamed in the PRD must be renamed in the roadmap), both files'
anchors complete the ONE `## Answer fidelity` and `## Roadmap milestones`
sections of the notes, and amend mode's diff discipline spans both files at
once. The parallelism in this skill is in the survey and the review, not in
the write.

### Review

Spawn the reviewer (`phase="reviewer"`) with ONLY artifact references (the two files,
the ticket, the git diff) — never the author's reasoning. Its `<inputs>` also carry
the iteration's authoring notes and `<partition>/clarifications.json`, and its
`<constraints>` also carry `prd`, `roadmap`, `required_sections`,
`audience_style_profile` (all declared above in the survey task example — the
same eight-section list the author was instructed to write, so the structure
gate has no second, driftable copy), and `repo_root` (the consumer repo root,
for the plan-conformance code-evidence family). In amend mode, the reviewer
itself derives the `--added-heading` values its plan-conformance check needs
from its own `git diff -- "<prd>" "<roadmap>"` (already dimension 8's
mechanism): every `+###`/`+####` heading line added to `roadmap.md`. It
re-reads everything fresh and checks, all findings blocking:

- all eight required `prd.md` sections present and non-empty, plus `roadmap.md`;
- every feature traces to at least one goal; no orphan features, no goal without a
  feature or an explicit deferral;
- every goal has at least one **measurable** success metric (value + unit +
  timeframe; "improve UX" fails);
- nothing in features, NFRs, or roadmap contradicts the stated constraints or the
  out-of-scope list;
- roadmap milestones map to intended epics and cover all Must-have features;
- every committed roadmap milestone resolves to **exactly one release
  version** (**0 orphan milestones**) — the mapping-table coverage sub-check
  (G17 100%-mapping metric); a milestone with zero or more than one mapped
  version is a blocking finding;
- amend mode: `git diff` shows only the intended sections changed.

**Reviewer slices — every iteration, the default.** The reviewer has eleven
check dimensions (numbered in `create-prd-reviewer.md`), so it always runs as
three slices, each a fresh instance of `acs:create-prd-reviewer` whose task
carries `slice="<id>"` and `<constraint name="dimensions">` naming the
dimension numbers it owns, beside every input and constraint above:

| Slice | Dimensions | Owns the run of |
|---|---|---|
| `substance` | 2 feature → goal traceability, 3 measurable success metrics, 4 prioritization discipline, 5 constraint consistency, 11 audience-style | the fresh semantic read of `prd.md` and `roadmap.md` |
| `floor` | 1 required sections, 7 plan conformance, 10 structure | the deterministic floor: `prd_conformance_check.py` (the three-family check, whose code-evidence family re-opens every citation through the shared citation-check helpers it imports) and `structure_lint.py` — each run in this slice only, exactly once per iteration |
| `delta` | 6 roadmap coverage, 8 amend-mode diff discipline, 9 iteration 2+ regression check | `git diff -- "<prd>" "<roadmap>"` and the re-verification of every prior finding |

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
  --out <partition>/steps/create-prd/iter-<n>/reviewer.md \
  <partition>/steps/create-prd/iter-<n>/reviewer-substance.md \
  <partition>/steps/create-prd/iter-<n>/reviewer-floor.md \
  <partition>/steps/create-prd/iter-<n>/reviewer-delta.md \
  <partition>/steps/create-prd/iter-<n>/reviewer-dedup.md
```

**Pass rule for sliced reviewers:** the iteration passes only if EVERY slice
returned `status="completed"` with zero blocking findings. Any slice's blocking
finding blocks the iteration. A slice that failed or returned no usable result
fails the iteration — never "pass with a missing slice"; re-run that slice
once, and if it fails again the iteration counts as failed with its error as a
finding.

Zero findings across all slices = pass -> Deliver. The findings that go on
are the de-duplicated set. Findings -> route every
finding of every slice verbatim into the next iteration's author `<task>`
`<context>`; the surveyor does not re-run — the author authors the remediation,
and the run continues author -> review.
After iteration 3 with findings remaining: STOP — final status `failed`,
findings recorded; go to Finish (no PR is opened).

## Deliver the docs-only PR

Only after the reviewer passes:

```bash
git add "<prd>" "<roadmap>"
git commit -m "<rendered formats.commit_message>"      # default {ticket_id} {summary}, e.g. "SHOP-1 Add product requirements document and roadmap"
git push -u origin "<branch>"
```

Then follow `${CLAUDE_PLUGIN_ROOT}/skills/create-prd/references/delivery-pr.md` for the
label, the rendered title, the body template, the pre-open self-check and
`gh pr create` — the mechanics every delivery-ticket skill shares. Three
things are this run's own:

- **Where the body lives.** Write the filled body to
  `steps/create-prd/pr-body.md`, and pass that path as
  `--body-file` to both the self-check and `gh pr create`.
- **What goes in it**, beyond the template's placeholders: Changes = the PRD
  files added or amended; Test plan = the review dimensions checked; mark
  TDD/coverage checklist items `N/A (docs-only PR)`. The default title renders
  e.g. `Amend PRD: add org-level enforcement policy`.
- **Reading the number back**: `gh pr view "<branch>" --json number,url`.
  Record the PR number, URL, and branch for the result document.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list --ticket <ticket-id>`
and reuse any recorded answer — re-asking an answered question is a defect.
When ≥2 clarifications are open, present them to the user in ONE grouped
interaction (e.g. a single AskUserQuestion containing all open questions as a
numbered list), not serial round-trips — one interaction per question wastes
user time. The open questions of ALL surveyor slices are one batch: wait for
every slice, then ask them in that ONE grouped interaction (a question two
slices raise word for word is asked once). Record each answer as its own `clarify.py add` entry (one `C-<n>`
per question, `--source` preserved). Never skip a question, merge two questions
into one entry, or auto-answer a question outside the existing
`--source assumption --rationale "..."` rule.
Record every Q&A — obtained interactively or relayed in a /ship brief — with
`clarify.py add --skill create-prd --question "..." --answer "..." --ticket <ticket-id>`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`. If the user is unavailable or says "you decide": record the
decision with `--source assumption --rationale "..."` — assumptions surface
in the completion report's Findings and the PR body until a user confirms.
Before a needs_input handoff, record the outgoing questions as `open`
(`clarify.py add` without `--answer`).

- **Greenfield**: elicit the definition from the user — vision, problem, personas,
  goals with measurable success metrics, prioritized features (MoSCoW), product NFRs,
  constraints, out-of-scope. Batch questions (AskUserQuestion or plain questions);
  when `$ARGUMENTS` already carries notes, propose drafts to confirm instead of
  interrogating from zero.
- **Brownfield**: present the reverse-engineered baseline and ask ONLY the open
  points the surveyor flagged.
- **Amend**: confirm exactly which sections change and why before the author writes.
- Ask only when genuinely ambiguous; never invent product facts. If you
  genuinely cannot reach the user (e.g. a non-interactive run), return a
  `<handoff skill="create-prd" ticket-id="<id>" status="needs_input">` with
  `<questions>` instead of guessing.

## Context pressure

If your context is running low mid-run: flush in-flight work and soft context (user
answers, decisions, partial findings, gotchas) to
`steps/create-prd/handoff-context.md`, then run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --ticket <ticket-id> --summary "<done / in-flight / next / decisions>"
```

and tell the user the printed `continue_with` command. Never burn the last of the
context on work that would be lost.

## Finish

MANDATORY final step — never skipped, also on failure.

1. Write `steps/create-prd/result.json` per the result-document contract
   (INTERNALS.md), with the canonical `states` keys for create-prd — `prd` and `pr`,
   exact names:

   ```json
   {
     "status": "completed",
     "summary": "PRD created and docs-only PR opened",
     "states": {
       "prd": {"path": "docs/product", "files": ["docs/product/prd.md", "docs/product/roadmap.md"]},
       "pr": {"number": 12, "url": "https://github.com/acme/shop/pull/12", "branch": "task/MAR-51-amend-prd-add-org-enforcement-policy"}
     },
     "findings": [],
     "errors": []
   }
   ```

   On failure keep whatever is true: status `failed`, remaining reviewer findings in
   `findings`, `states.prd` if the files were written, NO `states.pr` if no PR was
   opened, and the reason in `summary`.

2. Run the post-hook:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-prd.py" --result-file "<the result.json you just wrote>"
   ```

   It finalizes the run entry, updates `run.json` / `tickets-index.json`,
   flips the delivery ticket to `in_review` (PR recorded), and releases the
   `.lock`.

3. Report a compact summary to the user: delivery ticket id, mode
   (greenfield/brownfield/amend), files written, PR URL — and tell them to review the
   PR themselves, then run `/acs:merge-pr <delivery-ticket-id>` to land it.
   `/acs:create-architecture` is unblocked once the PRD exists. Under /acs:ship,
   return ONLY the `<handoff>` XML as your final message: status, summary <=1KB,
   artifact refs, next-step.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty; under /acs:ship your final message is the `<handoff>` XML instead — this report is for direct invocations:

```markdown
## /acs:create-prd · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: PRD files written/amended (`<prd>`, `<roadmap>`); delivery ticket id; PR number/URL
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <partition files, repo paths, branch, PR URL>
- **Metrics**: iterations <n>/<cap> · <wall time>
- **Next**: `/acs:merge-pr <ticket-id>` after reviewing the docs PR; then `/acs:create-architecture`
```
