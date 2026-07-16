---
name: create-requirements
description: Bootstrap or amend the consumer requirements/ doc set (functional + non-functional, one file per feature/item) — brownfield reverse-engineers it from the existing codebase (architecture-aware, code-cited, DRAFT), greenfield elicits it interactively, and amend augments only absent/ungrounded areas — shipped as a docs-only PR on its own delivery ticket. Use to bootstrap living requirements on an existing codebase, or to refresh the set after a gap is found.
argument-hint: "[delivery-ticket-id to resume | focus notes]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-requirements. You produce or amend the
consumer `requirements/` doc set — one file per functional feature and one per
non-functional item, in the functional/non-functional layout `/acs:code`'s
living-requirements merge already writes into — at `settings.requirements_path`
(default `docs/requirements`), resolved into `<requirements_path>/<functional_subdir>/`
and `<requirements_path>/<non_functional_subdir>/` via `settings.requirements_layout`
(defaults `functional`/`non-functional`; never hardcode these literals — always
read them from settings). You ship it yourself as a docs-only PR on a fresh
delivery ticket — `/acs:code` and `/acs:create-pr` are NOT involved. You
orchestrate planner/executor/verifier subagents; you never write requirement
content yourself.

## Start

MANDATORY first action. Pick the form by inspecting `$ARGUMENTS`:

- `$ARGUMENTS` contains a ticket id matching the repo prefix (e.g. `SHOP-1` — you are
  resuming an interrupted or handed-off delivery ticket):

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/skill-start.py" --skill create-requirements --ticket <ticket-id>
  ```

- Otherwise (fresh bootstrap or amendment — every run gets a NEW delivery ticket):

  Before calling `skill-start.py --allocate`, detect whether this is an **amend**
  run by checking if the resolved `<requirements_path>/<functional_subdir>/` or
  `<non_functional_subdir>/` already holds files (a substantially-populated set).
  This mirrors the planner's amend definition (see Plan below).

  - **Amend mode with a usable `$ARGUMENTS` request**: pass a `--title` flag:

    ```bash
    python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/skill-start.py" \
      --skill create-requirements --allocate \
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
    python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/skill-start.py" --skill create-requirements --allocate
    ```

  `--allocate` creates the delivery ticket (type `task`, built-in title
  **"Product requirements doc set"**, `PRODUCT_TICKET_TITLES["create-requirements"]`,
  overridable via `--title`), its workspace partition, the `.lock`, the session
  pointer, and the `in_progress` run entry.

If skill-start exits non-zero: STOP and surface its stderr verbatim.

Parse the printed context JSON. Key fields: `partition`, `ticket_id`, `ticket`,
`settings` (`requirements_path`, `requirements_layout`, `formats`), `models`,
`reconcile`, `handoff_summary`, `post_hook`.

If `settings.models.coordinator` is set, surface a one-line notice that it governs the
/acs:ship coordinator's own session — under /acs:ship this skill is invoked directly
in that session (no separate per-step agent for the key to apply to), and a directly
typed invocation runs in the user's session on the session's model. Never silently diverge.

Keep the free text of `$ARGUMENTS` (focus notes, amendment request): it is planner input.

## Resume & reconcile

If `context.reconcile` is true, verify recorded progress against reality BEFORE
continuing:

1. Re-read `<partition>/phases/create-requirements/iter-*-*.xml` and
   `<partition>/create-requirements-state.json` to see which phases completed.
2. Re-read the `<requirements_path>` tree against recorded executor claims — does
   the actual `functional/`/`non-functional/` file set match what the recorded
   executor results claim?
3. Check delivery progress: does the delivery branch exist
   (`git branch --list "<branch>"` / `git ls-remote --heads origin "<branch>"`)? Was a
   PR already opened (`gh pr list --head "<branch>" --json number,url`)?
4. Continue from the first unfinished phase. If verified docs already pass and the PR
   is open, skip straight to Finish with the recorded references.

If `context.handoff_summary` exists, read it (and
`<partition>/phases/create-requirements/handoff-context.md` if present), do a light
reconcile of the same checks, and continue from where it points.

## Reflection loop

Plan -> execute -> verify, max 3 iterations. Spawn subagents with the Agent tool:
`subagent_type` `acs:create-requirements-planner` / `acs:create-requirements-executor` /
`acs:create-requirements-verifier` (fall back to the un-namespaced name if the runtime
rejects the namespaced one). Apply `context.models.<role>.model` / `.effort` at spawn
when not `"inherit"`; if the runtime rejects the model/effort, FAIL the run with that
error — no silent fallback.

All messages follow `schemas/acs-messages.xsd`. Validate EVERY message you send and
receive:

```bash
echo "<task ...>...</task>" | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/validate_xml.py" -
```

On an invalid message, re-request it once; if still invalid, fail the run with the
validation error recorded in `errors`. Persist every phase output to
`<partition>/phases/create-requirements/iter-<n>-<phase>.xml` at the phase boundary
BEFORE starting the next phase. Decomposition is YOURS alone — subagents never spawn
subagents.

### Plan

The planner's first job is mode classification, keyed on whether
`<requirements_path>` already holds functional/non-functional content:

- **brownfield** (headline) — the requirements set is absent or sparse AND the
  repo has real code. Plan to reverse-engineer per-area requirements from the
  codebase (architecture-aware feature-area enumeration with a codebase-inventory
  fallback), code-cited and marked DRAFT.
- **amend** — the requirements set is already substantially populated. Plan a
  surgical augmentation: which absent/ungrounded area files gain new content,
  which existing files are preserved byte-for-byte.
- **greenfield** — no meaningful codebase to reverse-engineer AND the set is
  absent, so each elicited area maps to a `<functional_subdir>/<feature>.md`
  (behavioral feature) or `<non_functional_subdir>/<item>.md` (NFR item) target,
  DRAFT-marked. Plan the elicitation: per candidate feature area, the behavior
  it must have (a functional requirement), and per candidate quality concern,
  the constraint it must meet (a non-functional requirement) — mirroring
  create-prd's greenfield elicitation plan. Never silently fall through to
  brownfield and never invent a product fact the user has not confirmed.

The planner also runs the shared ADR-0012 design-time doc-consistency step; any
findings surface through the "Clarification ledger first" mechanism below (User
interaction).

**G36 declaration (AC-6).** Every plan/execute/verify task's `<constraints>` carries:

- `required_sections` — declared **per produced area file**, from the
  planner-approved outline. There is no single fixed section skeleton across all
  files (each feature/item file's sections follow the existing living-requirements
  prose format); the planner names the concrete heading list for each file it plans.
- `audience_style_profile` — always `engineers (behavioral-contract prose)`, the
  same constraint-passing mechanism `create-principles/SKILL.md` and
  `create-principles-verifier.md` use for their own G36 gate.

**Per-file format (finalized).** Both `<functional_subdir>/<feature>.md` and
`<non_functional_subdir>/<item>.md` open with the `DRAFT — human-confirm-required`
marker line, then follow the existing living-requirements prose format — the
`MUST` / `SHOULD` / `MAY` / `[OPEN]` / `[ASSUMPTION]` vocabulary — with NO fixed
universal heading skeleton (design Decision B-revised). The planner names the
concrete `required_sections` heading list per file in its outline; this
subsection documents that as the finalized per-file format rather than an
implicit convention. No new template file is introduced — the
functional/non-functional model itself is the format.

Example task (fill real values; `<context>` carries `$ARGUMENTS` and, on iteration
2+, the verifier findings to fix):

```xml
<task skill="create-requirements" phase="plan" ticket-id="SHOP-1" iteration="1">
  <objective>Classify mode (brownfield/greenfield/amend); enumerate or elicit feature areas; produce the per-area outline and the open questions for the user.</objective>
  <inputs>
    <file>/abs/workspace/acme-shop/SHOP-1/ticket.json</file>
    <file>/abs/repo/docs/requirements/README.md</file>
    <file>/abs/repo/docs/architecture/hld/c4-container.md</file>
  </inputs>
  <constraints>
    <constraint name="requirements_path">docs/requirements</constraint>
    <constraint name="functional_subdir">functional</constraint>
    <constraint name="non_functional_subdir">non-functional</constraint>
    <constraint name="required_sections">functional/checkout.md: MUST/SHOULD/MAY/[OPEN]/[ASSUMPTION]</constraint>
    <constraint name="audience_style_profile">engineers (behavioral-contract prose)</constraint>
  </constraints>
  <context>User focus notes from $ARGUMENTS; prior findings on iteration 2+.</context>
</task>
```

The planner returns a `<result>` with the outline in `<outputs>`-referenced files or
inline context, and open points in `<questions>`. Resolve those questions with the
user (see User interaction) BEFORE spawning the executor, and pass the answers in the
executor task's `<context>`.

### Execute

Prepare the delivery branch before the first execute (deterministic plumbing — you do
it, not the executor):

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

**Interactive-confirm, before you spawn the executor.** Present the planner's
DRAFT baseline — which feature areas will be elicited, extracted, or augmented,
and which are `[OPEN]` — and the open points via the clarify ledger (see User
interaction below), batched in one interaction when ≥2 questions are open.
An elicited, extracted, or augmented requirement is a **DRAFT baseline, never
authoritative without confirmation**: this confirmation step MUST complete
before you spawn the executor.

**The DRAFT / interactive-confirm discipline applies uniformly to all three
modes.** A requirement — elicited (greenfield), extracted (brownfield), or
augmented (amend) — is a DRAFT baseline the user must review and confirm before
it is authoritative; open points are surfaced for confirmation, and nothing is
written as authoritative without the human gate (C-22).

Spawn the executor (`phase="execute"`) with the approved outline, the user's answers,
and the mode. The executor — the only role that mutates the repo — writes,
per the mode:

- **brownfield/amend** — one `<requirements_path>/<functional_subdir>/<feature>.md`
  per behavioral feature and one `<requirements_path>/<non_functional_subdir>/<item>.md`
  per NFR item, classifying each requirement functional-vs-non-functional before
  writing it. Augment-only-absent: an existing area file is preserved byte-for-byte,
  never overwritten.
- **greenfield** — writes one
  `<requirements_path>/<functional_subdir>/<feature>.md` per elicited behavioral
  feature and one `<requirements_path>/<non_functional_subdir>/<item>.md` per
  elicited NFR item, from the plan's elicitation outline plus the user's
  answers; DRAFT-marked. No code-citation is required or expected (there is no
  code to cite) — every clause is grounded in the user's elicited answer, cited
  as such.

Typically ONE executor per run — the produced files are read once by a single
verifier pass. You MAY run multiple executors in parallel only when their target
area files cannot conflict (e.g. disjoint feature areas); the verifier always runs
after all executors finish and judges the combined result.

### Verify

Spawn the verifier (`phase="verify"`) with ONLY artifact references (the produced
files, the ticket, the git diff) — never the executor's reasoning. Its
`<constraints>` also carry `required_sections` (per produced area file) and
`audience_style_profile` (both declared above in the Plan task example). It
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
- plan conformance — the produced files realize the approved plan's outline;
- amend mode: `git diff` shows only the intended new/augmented area files —
  every existing area file is byte-identical;
- iteration 2+: every prior finding from `<context>` is actually fixed.

Zero findings = pass -> Deliver. Findings -> persist the verify XML, feed the
findings into the next plan/execute iteration. After iteration 3 with findings
remaining: STOP — final status `failed`, findings recorded; go to Finish (no PR is
opened).

## Deliver the docs-only PR

Only after the verifier passes:

```bash
git add "<requirements_path>/<functional_subdir>" "<requirements_path>/<non_functional_subdir>"
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
  amended; Test plan = the verifier dimensions checked; mark TDD/coverage checklist
  items `N/A (docs-only PR)`. Write the filled body to
  `<partition>/phases/create-requirements/pr-body.md` before the self-check below.
- **Pre-open self-check** — before `gh pr create`, self-check the rendered
  title and filled body with the helper's `check` subcommand (a deterministic
  CLI call, never a spawned subagent):

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pr-conventions.py" check \
    --title "<rendered title>" --body-file "<partition>/phases/create-requirements/pr-body.md" \
    --require-label ACS --pr-title-format "<settings.formats.pr_title>" \
    --sections "<settings.enforcement.pr_description_sections, comma-joined>" \
    --ticket-prefix <settings.ticket_prefix>
  ```

  On pass, proceed to `gh pr create` unchanged. On failure, this check
  blocks/retries: apply a bounded local re-render/re-check (up to 2
  attempts) rather than opening a non-conforming PR; if still failing after
  the bounded retries, STOP — do not call `gh pr create` — surface the
  blocking finding with the failing heading(s)/detail(s) in the result
  document.

```bash
gh pr create --base "$DEFAULT_BRANCH" --head "<branch>" \
  --title "<rendered title>" \
  --body-file "<partition>/phases/create-requirements/pr-body.md" \
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
user time. Record each answer as its own `clarify.py add` entry (one `C-<n>`
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
  human-confirm-required) and ask ONLY the open points the planner flagged — an
  extracted requirement is never authoritative without confirmation.
- **Amend**: confirm exactly which absent/ungrounded area files are augmented and
  why before executing; every other area file is untouched.
- **Greenfield**: elicit the definition from the user and map it to
  `<functional_subdir>/<feature>.md` files (the feature list — what the
  product/system does) and `<non_functional_subdir>/<item>.md` files (the NFR
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
`<partition>/phases/create-requirements/handoff-context.md`, then run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --ticket <ticket-id> --summary "<done / in-flight / next / decisions>"
```

and tell the user the printed `continue_with` command. Never burn the last of the
context on work that would be lost.

## Finish

MANDATORY final step — never skipped, also on failure.

1. Write `<partition>/phases/create-requirements/result.json` per the result-document
   contract (INTERNALS.md), with the canonical `states` keys for create-requirements —
   `requirements` and `pr`, exact names:

   ```json
   {
     "status": "completed",
     "stop_reason": "Requirements doc set produced/amended and docs-only PR opened",
     "states": {
       "requirements": {"path": "docs/requirements", "files": ["docs/requirements/functional/checkout.md"]},
       "pr": {"number": 12, "url": "https://github.com/acme/shop/pull/12", "branch": "task/MAR-51-product-requirements-doc-set"}
     },
     "findings": [],
     "errors": [],
     "tokens": {"input": 84000, "output": 21000},
     "cost_usd": 0.61
   }
   ```

   Estimate `tokens`/`cost_usd` for this run (all subagents + coordinator). On
   failure keep whatever is true: status `failed`, remaining verifier findings in
   `findings`, `states.requirements` if any files were written, NO `states.pr` if no
   PR was opened, and the reason in `stop_reason`.

2. Run the post-hook:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-requirements.py" --ticket <ticket-id> --result-file "<partition>/phases/create-requirements/result.json"
   ```

   It finalizes the run entry, updates `pipeline-state.json` / `tickets-index.json` /
   `metrics.json`, flips the delivery ticket to `in_review` (PR recorded), and
   releases the `.lock`.

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
- **Status**: <status> — <stop_reason>
- **Results**: requirements area files written/amended at `requirements_path`; delivery ticket id; PR number/URL
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <partition files, repo paths, branch, PR URL>
- **Metrics**: iterations <n>/3 · <wall time> · ~<tokens in/out> · ~$<cost_usd>
- **Next**: `/acs:merge-pr <ticket-id>` after reviewing the docs PR
```
