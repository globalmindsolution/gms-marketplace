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
orchestrate executor/verifier subagents — execute -> verify, no planner
(ADR-0092); you never write requirement content yourself.

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
  This mirrors the executor's amend definition (see Execute below).

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

Keep the free text of `$ARGUMENTS` (focus notes, amendment request): it is executor input.

## Resume & reconcile

If `context.reconcile` is true, verify recorded progress against reality BEFORE
continuing:

1. Re-read `steps/create-requirements/iter-*-*.xml` and
   `<partition>/create-requirements-state.json` to see which phases completed.
2. Re-read the `<requirements_path>` tree against recorded executor claims — does
   the actual `functional/`/`non-functional/` file set match what the recorded
   executor results claim?
3. Check delivery progress: does the delivery branch exist
   (`git branch --list "<branch>"` / `git ls-remote --heads origin "<branch>"`)? Was a
   PR already opened (`gh pr list --head "<branch>" --json number,url`)?
4. Continue from the first unfinished phase. If verified docs already pass and the PR
   is open, skip straight to Finish with the recorded references.
5. There is no plan artifact to reuse: an execute with no verify → verify it;
   a verify with findings and no later execute → execute with those findings
   as `<context>`. The executor's authoring notes (`iter-<n>-authoring.md`)
   belong to their iteration.

If `context.handoff_summary` exists, read it (and
`steps/create-requirements/handoff-context.md` if present), do a light
reconcile of the same checks, and continue from where it points.

## Reflection loop — execute -> verify, no planner

The loop is execute -> verify, max 3 iterations. There is no plan phase:
iteration 1's executor classifies the mode, enumerates or elicits the
feature areas, writes its authoring notes (the outline, the open points),
and — once the DRAFT baseline is confirmed — authors the area files from
them; the verifier judges the result fresh. On iterations 2-3 the verifier's
findings go verbatim into the next executor `<task>` `<context>` and the
executor authors the remediation. Spawn subagents with the Agent tool:
`subagent_type` `acs:create-requirements-executor` /
`acs:create-requirements-verifier` (fall back to the un-namespaced name if the runtime
rejects the namespaced one). Apply `context.models.<role>.model` / `.effort` at spawn
when not `"inherit"`; if the runtime rejects the model/effort, FAIL the run with that
error — no silent fallback.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops (`for i in $(seq 1 40); do
sleep 15; done` and its kin), which wait a fixed ten minutes whatever the
agent did and spent a whole 1800s setup on the 2026-09-15 release gate.

**What an iteration counts:** one execute -> verify round.
`/acs:create-requirements` has no path-driven verify-depth selection: the
cap is a fixed 3 on every run.

All messages follow `schemas/acs-messages.xsd`. Validate EVERY message you send and
receive:

```bash
echo "<task ...>...</task>" | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/validate_xml.py" -
```

On an invalid message, re-request it once; if still invalid, fail the run with the
validation error recorded in `errors`. Persist every phase output to
`steps/create-requirements/iter-<n>-<phase>.xml` at the phase boundary
BEFORE starting the next phase. The executor's own artifacts are
`iter-<n>-authoring.md` (Mode & evidence; Requirement outline; Open
questions; Risks; Verifier checklist) and `iter-<n>-execute.json`; every
iteration's verifier `<inputs>` name that iteration's authoring notes.
Decomposition is YOURS alone — subagents never spawn subagents.

### Execute — iteration 1 surveys before it writes

The executor's first job on iteration 1 is mode classification, keyed on whether
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
  create-prd's greenfield elicitation. Never silently fall through to
  brownfield and never invent a product fact the user has not confirmed.

The executor also runs the shared ADR-0012 design-time doc-consistency step;
any findings surface through the "Clarification ledger first" mechanism below
(User interaction). It records the classification, the outline and the open
points in its authoring notes and — unless the task `<context>` already
carries the confirmation — returns `needs_input` with the DRAFT baseline
before writing any area file (see Interactive-confirm below).

**G36 declaration (AC-6).** Every execute/verify task's `<constraints>` carries:

- `required_sections` — declared **per produced area file**, from the
  confirmed outline in the executor's authoring notes. There is no single fixed
  section skeleton across all files (each feature/item file's sections follow
  the existing living-requirements prose format); the executor names the
  concrete heading list for each file in its notes, and the coordinator carries
  that list into the iteration's verify task and every later execute task.
- `audience_style_profile` — always `engineers (behavioral-contract prose)`, the
  same constraint-passing mechanism `create-principles/SKILL.md` and
  `create-principles-verifier.md` use for their own G36 gate.

**Per-file format (finalized).** Both `<functional_subdir>/<feature>.md` and
`<non_functional_subdir>/<item>.md` open with the `DRAFT — human-confirm-required`
marker line, then follow the existing living-requirements prose format — the
`MUST` / `SHOULD` / `MAY` / `[OPEN]` / `[ASSUMPTION]` vocabulary — with NO fixed
universal heading skeleton (design Decision B-revised). The executor names the
concrete `required_sections` heading list per file in its notes' outline; this
subsection documents that as the finalized per-file format rather than an
implicit convention. No new template file is introduced — the
functional/non-functional model itself is the format.

Example iteration-1 task (fill real values; `<context>` carries `$ARGUMENTS`
and, on the re-run after interactive-confirm, the user's recorded answers):

```xml
<task skill="create-requirements" phase="execute" ticket-id="SHOP-1" iteration="1">
  <objective>Classify mode (brownfield/greenfield/amend); enumerate or elicit feature areas; record the per-area outline and the open questions in the authoring notes; once the baseline is confirmed, write the area files from them.</objective>
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
  <context>User focus notes from $ARGUMENTS.</context>
</task>
```

On its survey pass the executor returns `needs_input` with the outline in its
authoring notes (`<outputs>`) and the open points in `<questions>`. Resolve
those questions with the user (see User interaction) and re-run execute for
the same iteration with the answers in `<context>`.

### Execute — the write

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

**Interactive-confirm, between the executor's survey and its write.** Present
the executor's DRAFT baseline — which feature areas will be elicited,
extracted, or augmented, and which are `[OPEN]` — and the open points via the
clarify ledger (see User interaction below), batched in one interaction when
≥2 questions are open. An elicited, extracted, or augmented requirement is a
**DRAFT baseline, never authoritative without confirmation**: this
confirmation step MUST complete before the executor writes an area file — it
is what the `needs_input` round-trip above exists for.

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
after all executors finish and judges the combined result. On iterations 2-3 the
verifier's findings go verbatim into the executor `<task>`'s `<context>`, with no
plan phase in between.

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

Zero findings = pass -> Deliver. Findings -> persist the verify XML, feed them
verbatim into the next iteration's executor `<task>` `<context>` — with no
plan phase in between, and re-run execute -> verify. After
iteration 3 with findings remaining: STOP — final status `failed`, findings
recorded; go to Finish (no PR is opened).

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
  `steps/create-requirements/pr-body.md` before the self-check below.
- **Pre-open self-check** — before `gh pr create`, self-check the rendered
  title and filled body with the helper's `check` subcommand (a deterministic
  CLI call, never a spawned subagent):

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pr-conventions.py" check \
    --title "<rendered title>" --body-file "steps/create-requirements/pr-body.md" \
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
  human-confirm-required) and ask ONLY the open points the executor's survey flagged — an
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
     "stop_reason": "Requirements doc set produced/amended and docs-only PR opened",
     "states": {
       "requirements": {"path": "docs/requirements", "files": ["docs/requirements/functional/checkout.md"]},
       "pr": {"number": 12, "url": "https://github.com/acme/shop/pull/12", "branch": "task/MAR-51-product-requirements-doc-set"}
     },
     "findings": [],
     "errors": []
   }
   ```

   On failure keep whatever is true: status `failed`, remaining verifier findings in
   `findings`, `states.requirements` if any files were written, NO `states.pr` if no
   PR was opened, and the reason in `stop_reason`.

2. Run the post-hook:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-requirements.py" --ticket <ticket-id> --result-file "steps/create-requirements/result.json"
   ```

   It finalizes the run entry, updates `run.json` / `tickets-index.json` /
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
- **Metrics**: iterations <n>/<cap> · <wall time> · ~<tokens in/out> · ~$<cost_usd>
- **Next**: `/acs:merge-pr <ticket-id>` after reviewing the docs PR
```
