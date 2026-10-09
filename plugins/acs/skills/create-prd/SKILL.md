---
name: create-prd
description: Define or amend the product PRD — vision, problem, personas, goals with measurable success metrics, prioritized features, NFRs, constraints — plus a roadmap, left as local changes for /acs:create-pr to commit and open as a PR. Use when starting a product, onboarding acs onto an existing codebase, or when scope changes require a PRD amendment. Use for any request to write down what a product is, its problem, users and success metrics, or to amend its scope, priorities or roadmap — including when leadership cuts or reprioritizes a feature the existing PRD still lists. Invoke it directly on such a request — it confirms scope and gathers what it needs from the user itself, so there is nothing to ask before running it.
argument-hint: "[ticket-id] [documents…] [product notes | amendment request]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-prd. You produce or amend the PRD doc set in
the consumer repo — wherever the repo already keeps its PRD, else at
`docs/product/`: the hub `prd.md`, one PRD per feature at
`features/<slug>/prd.md`, and `roadmap.md` (ADR-0142) — as a **ticketless
run**, and you leave the documents as uncommitted changes in the working tree:
no ticket, no branch, no commit, no PR (ADR-0127). `/acs:create-pr`, given a
prompt (e.g. `/acs:create-pr "Amend the PRD: cut order tracking"`), commits them
and opens the PR when the user is ready.
You orchestrate three subagents — surveyor → authors → review: a read-only
surveyor establishes the mode, the outline, the feature set and the open
questions, you put the questions to the user, authors write the documents from
the notes and the answers, and a reviewer judges them fresh. You never write
the PRD content yourself. Every phase fans out: the survey runs as parallel
surveyor slices over disjoint areas of the repo when a brownfield or amend code
survey spans two or more of them, the write runs the `hub` author first and then
one author per feature in parallel, and the review always runs as two parallel
reviewer slices over disjoint check dimensions, beside the deterministic floor
you run yourself.

## Start

MANDATORY first action. Locate the repo's PRD the way any session finds a
document: CLAUDE.md and whatever docs index it or the repo points at (e.g.
`docs/README.md`), then a Glob/Grep for `prd.md` or a PRD by content. Found →
this is an **amend** run; that file is `<prd>` and its roadmap (located the same
way, else `roadmap.md` beside it) is `<roadmap>`. Not found → ask acs where the
PRD folder is — `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" docs where
--doc living:prd` — and `<prd>` = `<path>/prd.md`, `<roadmap>` =
`<path>/roadmap.md`. The PRD is a living document, always shared, but acs never
creates a new docs folder without asking (ADR-0132): when `needs` names
`location` (`location_source: default` — no `docs.prd_dir` setting, no existing
folder), the folder is a question in the ONE grouped ask (User interaction) —
use `proposed_path` (e.g. `docs/product`) or give another repo-relative folder,
no keep-local option — saved for the team with `acs.py docs decide --location
prd=<folder>`; until then the author writes nothing there. This mirrors the
surveyor's amend definition (see Survey below). Then run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-prd --args "$ARGUMENTS"
```

A PRD run needs no ticket: `step start` opens a run over the invocation — or
resumes this checkout's interrupted create-prd run, so re-running the skill
after a handoff picks up where it stopped — and the post-hook concludes it.
Nothing is minted: no delivery ticket, no tracker sync, no branch.

If `acs step start` exits non-zero: STOP and surface its stderr verbatim.

Parse the printed context JSON. Key fields: `partition`, `run_id`,
`settings` (`ticket_prefix`, `parallel.max_agents`), `agents` (agent name to
spawn per role), `reconcile`, `handoff_summary`, `checkout_root`.

**Requirements: `context.requirements` / `acs.py requirements show` — a ticket
id, documents and a prompt are only where they came from.** The product notes or
amendment request (the prompt), any documents `$ARGUMENTS` named — a brief, a
spec, a PDF or an image, in the repo or attached from outside it (copied into
the run; PDFs and images cited for you to Read) — and a ticket when one was
named, are all recorded in the run's `requirements.md` (`requirements.path`):
it is surveyor and author input, named by path in their `<inputs>`. `<prd>` and `<roadmap>` are the repo-relative paths
every later section uses; `<prd_dir>` is the folder holding `<prd>`, and a
feature's PRD is `<prd_dir>/features/<slug>/prd.md`.

## Resume & reconcile

If `context.reconcile` is true, or `context.handoff_summary` exists, read
`${CLAUDE_PLUGIN_ROOT}/skills/create-prd/references/resume.md` and reconcile
BEFORE continuing; a fresh run skips it.

## Reflection loop — surveyor → author → review

The loop is surveyor → author → review, max 3 iterations. Iteration 1 runs
the surveyor once: it classifies the mode, surveys the codebase or plans the
elicitation, and writes the authoring notes (the outline, the feature set, the open
questions, the three corroboration sections the review's deterministic floor parses)
read-only. You relay its open questions to the user, then spawn the authors, who
write the hub, the roadmap and the feature PRDs from the notes and the answers; the
reviewer judges the result fresh. On iterations 2-3 the reviewer's findings go
verbatim into the next author `<task>` `<context>` — each to the author that owns
the file — and the authors author the remediation — the surveyor never runs again;
its notes are the fixed baseline every later iteration is judged against.

**What an iteration counts:** one author -> review round (the hub and its feature
authors are one round). The survey belongs
to iteration 1 and is not a round of its own. `/acs:create-prd` has no
path-driven review-depth selection: the cap is a fixed 3 on every run.

| Role | Kind | Agent | Spawn as |
|------|------|-------|------------|
| surveyor | survey | `acs:create-prd-surveyor` | `context.agents.surveyor` |
| author | write | `acs:create-prd-author` | `context.agents.author` |
| reviewer | judge | `acs:create-prd-reviewer` | `context.agents.reviewer` |

Spawn subagents with the Agent tool: `subagent_type`
`acs:create-prd-surveyor` / `acs:create-prd-author` /
`acs:create-prd-reviewer` (fall back to the un-namespaced name if the runtime rejects
the namespaced one). Spawn each role under the name in `context.agents.<role>` — the plugin's
`acs:create-prd-<role>`, or the generated `acs-create-prd-<role>` copy
`acs step start` wrote where `settings.models` sets a model or effort for it.
Model and effort travel with that agent, so pass none of your own. If the runtime
rejects the agent, FAIL the run with that exact error — no silent fallback.

Read `${CLAUDE_PLUGIN_ROOT}/skills/create-prd/references/fan-out.md` before the
first spawn: the foreground rule, the message check, what is persisted at each
phase boundary, and the fan-out rules (slice ids, slice plans, the join, the
cap) every sliced phase follows.

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
<task skill="create-prd" phase="surveyor" iteration="1">
  <objective>Classify mode (greenfield/brownfield/amend) with evidence; record the prd.md and roadmap.md outline, the feature set (one slug per feature), the elicitation or reverse-engineering survey, the open questions for the user, and the `## Code evidence` / `## Answer fidelity` / `## Roadmap milestones` corroboration sections the review's deterministic floor parses in the authoring notes; write no repo file.</objective>
  <inputs>
    <file>/abs/repo/docs/product/prd.md</file>
    <file>/abs/repo/README.md</file>
  </inputs>
  <constraints>
    <constraint name="partition">/abs/workspace/acme-shop/runs/acs-create-prd-write-the-prd-3f9a</constraint>
    <constraint name="prd">docs/product/prd.md</constraint>
    <constraint name="roadmap">docs/product/roadmap.md</constraint>
    <constraint name="required_sections">Vision; Problem statement; Target users &amp; personas; Goals &amp; success metrics; Features (prioritized); Non-functional requirements; Constraints &amp; assumptions; Out of scope</constraint>
    <constraint name="feature_required_sections">Summary; Goals served; Requirements; Acceptance criteria; Dependencies; Out of scope</constraint>
    <constraint name="features_dir">docs/product/features</constraint>
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

Slice the survey only when the mode is brownfield or amend AND its code spans
**two or more disjoint top-level areas** of the repo; then read
`${CLAUDE_PLUGIN_ROOT}/skills/create-prd/references/survey-slices.md`.
Greenfield never slices, and code in one area runs the single surveyor above.

### Author — the hub, then one writer per feature

No branch is prepared: the authors write into the working tree on whatever
branch is checked out, and the documents stay there as uncommitted changes
(Delivery below).

The authors — the only roles that mutate the repo — write:

- `<prd>`, the hub, with EXACTLY the eight `required_sections`; **Features
  (prioritized)** (MoSCoW: Must/Should/Could/Won't) is the index, one bullet per
  feature linking its PRD and naming the goal(s) it serves.
- `<prd_dir>/features/<slug>/prd.md` for each feature — one document each,
  with the `feature_required_sections` and `R<n>` requirement ids.
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
- In amend mode: edit the documents in place, preserving untouched sections
  exactly (verify with `git diff` over the whole set); update `roadmap.md` only
  where the amendment changes it. The leading front-matter block is exempt from the byte-for-byte rule
  and is never an author's: they neither write, edit nor remove it (Versions below).

Each author completes the `## Answer fidelity` anchors against the text it
wrote. Should one return `needs_input` (a product fact the answers do not
settle), ask the user and re-run that author for the same iteration with the
answer in `<context>`.

**The hub is one author, and runs first.** `roadmap.md` derives from `prd.md`
(every milestone lists PRD features, every Must-have must land in a milestone)
and amend mode's diff discipline spans both, so no partition two writers could
own exists. The feature PRDs are disjoint, derive from the hub's index and run in
parallel after it. No integration pass follows: the index is the seam, and the
floor checks it.

Read `${CLAUDE_PLUGIN_ROOT}/skills/create-prd/references/documents.md` (the shapes)
and `${CLAUDE_PLUGIN_ROOT}/skills/create-prd/references/author-slices.md` (the
sequence) before the first author spawn.

### Versions — after every author result (ADR-0122, ADR-0130)

Every document of the set — `prd.md`, `roadmap.md` and each feature's `prd.md` —
is versioned: it opens with the front-matter block (`status`, `version`,
`tickets`) that `/acs:set-doc-status` later moves to `approved`. It is set ONLY
through `acs.py design`, by you, never by an author and never by hand.

Read `${CLAUDE_PLUGIN_ROOT}/skills/create-prd/references/versions.md` before
the first author spawn and after every author result: what to record where the
run started, and when each file's block is initialised, bumped or left alone.
A feature a run does not touch keeps its version.

### Review

Spawn the reviewer (`phase="reviewer"`) with ONLY artifact references (every
document of the set and the git diff) — never the author's reasoning. Its
`<inputs>` also carry the iteration's authoring notes, each feature's
`features/<slug>/notes.md` and `<partition>/clarifications.json`, and its
`<constraints>` also carry `prd`, `roadmap`, `features_dir`, `required_sections`,
`feature_required_sections`, `audience_style_profile` (all declared above in the
survey task example, so the structure gate has no second, driftable copy) and
`repo_root` (for the plan-conformance code-evidence family). It re-reads everything fresh,
and the review — its slices plus the floor you run — checks, all findings
blocking:

- all eight required `prd.md` sections present and non-empty, plus `roadmap.md`,
  and every feature PRD with its six sections; the Features index and the
  documents agree (each Must/Should/Could feature links an existing document,
  none is unlinked);
- every feature traces to at least one goal, in the hub's bullet and in its own
  PRD alike; no orphan features, no goal without a feature or an explicit deferral;
- every goal has at least one **measurable** success metric (value + unit +
  timeframe; "improve UX" fails);
- nothing in features, NFRs, or roadmap contradicts the stated constraints or the
  out-of-scope list;
- roadmap milestones map to intended epics and cover all Must-have features;
- every committed roadmap milestone resolves to **exactly one release
  version** (**0 orphan milestones**) — the mapping-table coverage sub-check
  (G17 100%-mapping metric); a milestone with zero or more than one mapped
  version is a blocking finding;
- amend mode: `git diff` shows only the intended sections changed — the
  leading front-matter block aside, which must show the version bumped (the
  version `versions-before.json` recorded + 1, status `proposed`);
- every document carries a valid version front-matter block (`acs.py design check`).

Read `${CLAUDE_PLUGIN_ROOT}/skills/create-prd/references/review-slices.md`
before every review: the two reviewer slices and your deterministic floor, the
de-duplication and join, and the pass rule for sliced reviewers.

Zero findings across all slices and the floor = pass -> Deliver. Otherwise route
every de-duplicated finding verbatim into the `<context>` of the author that owns
its file (author-slices.md); the surveyor does not re-run, and the run continues
author -> review. After iteration 3 with findings remaining: STOP — final status `failed`,
findings recorded; go to Finish (the files stay in the working tree as they are).

## Delivery

Only after the reviewer passes. Documents only, and they stay local: no branch,
no commit, no push, no PR — whichever branch is checked out (ADR-0127). Leave
the hub, the roadmap and the feature PRDs as uncommitted changes and record every path you wrote,
repo-relative, in result `states.files`. The final message lists those files and
points the user at `/acs:create-pr "<what the PRD change is>"` (e.g.
`/acs:create-pr "PRD for the wishlist feature"`) — given a prompt, it groups the
uncommitted changes by layer (the PRD its own commit), commits them on a branch
of their own and opens the PR when the user is ready.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list`
and reuse any recorded answer — re-asking an answered question is a defect.
When ≥2 clarifications are open, present them to the user in ONE grouped
interaction (e.g. a single AskUserQuestion containing all open questions as a
numbered list), not serial round-trips — one interaction per question wastes
user time. The open questions of ALL surveyor slices are one batch: wait for
every slice, then ask them in that ONE grouped interaction (a question two
slices raise word for word is asked once), with the PRD folder when Start's
`docs where` named `location`. Record each answer as its own `clarify.py add` entry (one `C-<n>`
per question, `--source` preserved). Never skip a question, merge two questions
into one entry, or auto-answer a question outside the existing
`--source assumption --rationale "..."` rule.
Record every Q&A — obtained interactively or relayed in a /ship brief — with
`clarify.py add --skill create-prd --question "..." --answer "..."`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`. If the user is unavailable or says "you decide": record the
decision with `--source assumption --rationale "..."` — assumptions surface
in the completion report's Findings until a user confirms.
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
  `<handoff skill="create-prd" status="needs_input">` with
  `<questions>` instead of guessing.

## Context pressure

If your context is running low mid-run: flush in-flight work and soft context (user
answers, decisions, partial findings, gotchas) to
`steps/create-prd/handoff-context.md`, then run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --summary "<done / in-flight / next / decisions>"
```

and tell the user the printed `continue_with` command (re-running this skill
resumes the run, see Start). Never burn the last of the context on work that
would be lost.

## Finish

MANDATORY final step — never skipped, also on failure.

1. Write `steps/create-prd/result.json` through `acs.py write` (never the Write tool) per
   the result-document contract (INTERNALS.md), with the canonical `states` keys for
   create-prd — `prd` and `files`, exact names:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" write steps/create-prd/result.json <<'ACS_EOF'
   {
     "status": "completed",
     "summary": "PRD created and reviewed; left as local changes",
     "states": {
       "prd": {"path": "docs/product"},
       "files": ["docs/product/prd.md", "docs/product/roadmap.md"]
     },
     "findings": [],
     "errors": []
   }
   ACS_EOF
   ```

   `files` lists EVERY repo path written, repo-relative, each feature PRD
   (`docs/product/features/<slug>/prd.md`) too —
   `/acs:create-pr` groups exactly these into the PRD's commit. On failure keep whatever is true:
   status `failed`, remaining reviewer findings in `findings`, `states.prd` and,
   in `states.files`, the files written so far, and the reason in `summary`.
   The front-matter changes are part of those same files; nothing else is
   written for them.

2. Run the post-hook:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-prd.py" --result-file "<the result.json you just wrote>"
   ```

   It finalizes the step, concludes the run `step start` opened, and releases
   the `.lock`.

3. Report a compact summary to the user: mode (greenfield/brownfield/amend)
   and the uncommitted files written — and tell them to review the files, then
   run `/acs:create-pr "<what the PRD change is>"` to commit them and open the PR.
   `/acs:create-architecture` can run on the local PRD straight away. Under /acs:ship,
   return ONLY the `<handoff>` XML as your final message: status, summary <=1KB,
   artifact refs, next-step.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty; under /acs:ship your final message is the `<handoff>` XML instead — this report is for direct invocations:

```markdown
## /acs:create-prd · <mode> · <status>

- **Ticket**: none — a ticketless run; the documents are delivered by `/acs:create-pr`
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: PRD files written/amended (`<prd>`, `<roadmap>` and the feature PRDs) with each one's status and version (`proposed v<n>`), and the folder when it was chosen in this run, left as uncommitted changes (`states.files`)
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <partition files; the uncommitted repo paths>
- **Metrics**: iterations <n>/<cap> · <wall time>
- **Next**: review the listed files, then `/acs:create-pr "<what the PRD change is>"` (e.g. `/acs:create-pr "PRD for the wishlist feature"`) to commit them and open the PR; once the team approves them, `/acs:set-doc-status approved prd`; `/acs:create-architecture` next
```
