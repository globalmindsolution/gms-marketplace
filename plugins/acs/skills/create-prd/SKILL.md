---
name: create-prd
description: Define or amend the product PRD — vision, problem, personas, goals with measurable success metrics, prioritized features, NFRs, constraints — plus a roadmap, shipped as a docs-only PR on its own delivery ticket. Use when starting a product, onboarding acs onto an existing codebase, or when scope changes require a PRD amendment. Invoke it directly on such a request — it confirms scope and gathers what it needs from the user itself, so there is nothing to ask before running it.
argument-hint: "[product notes | delivery-ticket-id to resume]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-prd. You produce or amend the PRD doc set
(`prd.md` + `roadmap.md`) in the consumer repo — wherever the repo already keeps
its PRD, else at `docs/product/` — under a fresh **delivery ticket**, and you ship
it yourself as a docs-only PR — `/acs:code` and `/acs:create-pr` are NOT involved.
You orchestrate executor/verifier subagents — execute -> verify, no planner
(ADR-0092); you never write the PRD content yourself.

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
  the conventional default. This mirrors the executor's amend definition (see
  Execute below).

  - **Amend mode with a usable `$ARGUMENTS` request**: pass a `--title` flag:

    ```bash
    python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs step start" \
      --skill create-prd --allocate \
      --title "Amend PRD: <≤~10-word summary of what changed>"
    ```

    A usable `$ARGUMENTS` request (clarification C-2): after stripping any leading
    delivery-ticket id (a token matching the repo prefix pattern, e.g. `MAR-51`),
    `$ARGUMENTS` contains free text describing what the amendment changes from which a
    short (about 10 words or fewer) summary can be formed. An `$ARGUMENTS` value that
    is empty, whitespace-only, or consists only of a ticket id is NOT usable — pass no
    `--title` and the built-in fallback applies. This is coordinator judgment, not
    parsing machinery; keep the free text of `$ARGUMENTS` as executor input (see below).

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
`settings` (`formats`, `ticket_prefix`), `models` (per-role model/effort),
`reconcile`, `handoff_summary`, `design`, `pipeline`, `post_hook`.

Keep the free text of `$ARGUMENTS` (product notes, amendment request): it is executor
input. `<prd>` and `<roadmap>` are the repo-relative paths every later section uses;
on the resume form, locate them the same way right after `acs step start`.

## Resume & reconcile

If `context.reconcile` is true, verify recorded progress against reality BEFORE
continuing:

1. Re-read `steps/create-prd/iter-*-*.xml` and
   `<partition>/create-prd-state.json` to see which phases completed.
2. Re-read `<repo>/<prd>` and `<repo>/<roadmap>` — does their content
   match what the recorded executor results claim?
3. Check delivery progress: does the delivery branch exist
   (`git branch --list "<branch>"` / `git ls-remote --heads origin "<branch>"`)? Was a
   PR already opened (`gh pr list --head "<branch>" --json number,url`)?
4. Continue from the first unfinished phase. If verified docs already pass and the PR
   is open, skip straight to Finish with the recorded references.
5. There is no plan artifact to reuse: an execute with no verify -> verify it;
   a verify with findings and no later execute -> execute with those findings
   as `<context>`. The executor's authoring notes (`iter-<n>/authoring.md`)
   belong to their iteration.

If `context.handoff_summary` exists, read it (and
`steps/create-prd/handoff-context.md` if present), do a light reconcile
of the same checks, and continue from where it points.

## Reflection loop — execute -> verify, no planner

The loop is execute -> verify, max 3 iterations. There is no plan phase:
iteration 1's executor classifies the mode, surveys the codebase or elicits
the product facts, writes its authoring notes (the outline, the open
questions, the three corroboration sections the verifier's floor parses),
and — once the open questions are answered — authors `prd.md` and
`roadmap.md` from them; the verifier judges the result fresh. On iterations
2-3 the verifier's findings go verbatim into the next executor `<task>`
`<context>` and the executor authors the remediation.

**What an iteration counts:** one execute -> verify round. `/acs:create-prd`
has no path-driven verify-depth selection: the cap is a fixed 3 in every
lane, and this ticket introduces none.

Spawn subagents with the Agent tool:
`subagent_type` `acs:create-prd-executor` /
`acs:create-prd-verifier` (fall back to the un-namespaced name if the runtime rejects
the namespaced one). Apply `context.models.<role>.model` / `.effort` at spawn when not
`"inherit"`; if the runtime rejects the model/effort, FAIL the run with that error —
no silent fallback.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops (`for i in $(seq 1 40); do
sleep 15; done` and its kin), which wait a fixed ten minutes whatever the
agent did and spent a whole 1800s setup on the 2026-09-15 release gate.

All messages follow `the SubagentStop hook's message check`. Validate EVERY message you send and
receive:

```bash
```

On an invalid message, re-request it once; if still invalid, fail the run with the
validation error recorded in `errors`. Persist every phase output to
`steps/create-prd/iter-<n>/<phase>.json` at the phase boundary BEFORE
starting the next phase. The executor's own artifacts are `iter-<n>/authoring.md`
(Mode & evidence; PRD outline; Roadmap outline; Code evidence; Answer fidelity;
Roadmap milestones; Open questions; Risks; Verifier checklist) and
`iter-<n>/execute.json`; every iteration's verifier `<inputs>` name that
iteration's authoring notes. Decomposition is YOURS alone — subagents never
spawn subagents.

### Execute — iteration 1 surveys before it writes

The executor's first job on iteration 1 is mode classification:

- **amend** — `<repo>/<prd>` already exists. Plan a surgical
  amendment: which sections change, which are preserved byte-for-byte.
- **brownfield** — no `prd.md`, but the repo contains real code. Plan to
  reverse-engineer a baseline PRD from the codebase and existing docs, listing the
  open points that need user confirmation.
- **greenfield** — empty/near-empty repo. Plan the elicitation: what to ask the user
  for vision, problem, personas, goals (+ measurable success metrics), prioritized
  features (MoSCoW), product NFRs, constraints, out-of-scope.

The executor also runs the shared ADR-0012 design-time doc-consistency step;
any findings surface through the "Clarification ledger first" mechanism below
(User interaction). It records the classification, the outline, the open
questions and the three corroboration sections in its authoring notes and —
unless the task `<context>` already carries the answers — returns
`needs_input` with the open questions before writing any file.

Example task (fill real values; `<context>` carries `$ARGUMENTS` and the user's
recorded clarification answers):

```xml
<task skill="create-prd" phase="execute" ticket-id="SHOP-1" iteration="1">
  <objective>Classify mode (greenfield/brownfield/amend); record the prd.md and roadmap.md outline, the elicitation or reverse-engineering survey, the open questions for the user, and the `## Code evidence` / `## Answer fidelity` / `## Roadmap milestones` corroboration sections the verifier's deterministic floor parses in the authoring notes; once the questions are answered, write prd.md and roadmap.md from them.</objective>
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
  <context>User notes from $ARGUMENTS; the user's recorded clarification answers.</context>
</task>
```

On its survey pass the executor returns `needs_input` with the outline in its
authoring notes (`<outputs>`) and the open points in `<questions>`. Resolve those
questions with the user (see User interaction) and re-run execute for the same
iteration with the answers in `<context>`.

### Execute — the write

Prepare the delivery branch before the first execute (deterministic plumbing — you do
it, not the executor):

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

Re-run the executor (`phase="execute"`, same iteration) with the user's answers and
the mode in `<context>`. On that pass the executor — the only role that mutates the
repo — writes:

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

Typically ONE executor — `prd.md` and `roadmap.md` are tightly coupled. You MAY run
two executors in parallel only when their outputs cannot conflict (e.g. iteration-2
fixes confined to disjoint files); the verifier always runs after all executors
finish and judges the combined result.

### Verify

Spawn the verifier (`phase="verify"`) with ONLY artifact references (the two files,
the ticket, the git diff) — never the executor's reasoning. Its `<inputs>` also carry
`<partition>/clarifications.json`, and its `<constraints>` also carry `prd`,
`roadmap`, `required_sections`, `audience_style_profile` (all declared above in the
execute task example — the same eight-section list the executor was instructed to write,
so the structure gate has no second, driftable copy), and `repo_root` (the consumer
repo root, for the plan-conformance code-evidence family). In amend mode, the
verifier itself derives the `--added-heading` values its plan-conformance check
needs from its own `git diff -- "<prd>" "<roadmap>"` (already dimension 8's
mechanism): every `+###`/`+####` heading line added to `roadmap.md`. It re-reads
everything fresh and checks, all findings blocking:

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

Zero findings = pass -> Deliver. Findings -> persist the verify XML, then route every
finding verbatim into the next iteration's executor `<task>` `<context>`, with no
plan phase in between — the executor authors the remediation, and the run
continues execute -> verify. After iteration 3 with findings remaining: STOP — final
status `failed`, findings recorded; go to Finish (no PR is opened).

## Deliver the docs-only PR

Only after the verifier passes:

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
  files added or amended; Test plan = the verifier dimensions checked; mark
  TDD/coverage checklist items `N/A (docs-only PR)`. The default title renders
  e.g. `[MAR-51] Amend PRD: add org-level enforcement policy`.
- **Reading the number back**: `gh pr view "<branch>" --json number,url`.
  Record the PR number, URL, and branch for the result document.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list --ticket <ticket-id>`
and reuse any recorded answer — re-asking an answered question is a defect.
When ≥2 clarifications are open, present them to the user in ONE grouped
interaction (e.g. a single AskUserQuestion containing all open questions as a
numbered list), not serial round-trips — one interaction per question wastes
user time. Record each answer as its own `clarify.py add` entry (one `C-<n>`
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
  points the executor's survey flagged.
- **Amend**: confirm exactly which sections change and why before executing.
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

   On failure keep whatever is true: status `failed`, remaining verifier findings in
   `findings`, `states.prd` if the files were written, NO `states.pr` if no PR was
   opened, and the reason in `summary`.

2. Run the post-hook:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-prd.py" --result-file "<the result.json you just wrote>"
   ```

   It finalizes the run entry, updates `run.json` / `tickets-index.json` /
   `metrics.json`, flips the delivery ticket to `in_review` (PR recorded), and
   releases the `.lock`.

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
- **Metrics**: iterations <n>/<cap> · <wall time> · ~<tokens in/out> · ~$<cost_usd>
- **Next**: `/acs:merge-pr <ticket-id>` after reviewing the docs PR; then `/acs:create-architecture`
```
