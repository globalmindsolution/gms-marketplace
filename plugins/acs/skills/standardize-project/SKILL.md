---
name: standardize-project
description: Audit an EXISTING repo against its principles_path/standards_path doc sets, hld/project-structure.md, and acs-readiness tooling (coverage/CI/pre-commit/e2e), then additively scaffold ONLY the missing docs/config/tooling as one reviewed PR -- never moving, renaming, deleting, or rewriting existing source. Structural gaps surface as recommended follow-up tickets, never auto-minted. Use on an existing codebase to bring it up to acs's structural/tooling expectations; the brownfield counterpart to the greenfield-only /acs:create-project.
argument-hint: "[delivery-ticket-id to resume | focus notes]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:standardize-project. On an EXISTING repo, you audit it
against `settings.principles_path`, `settings.standards_path`,
`<architecture_path>/hld/project-structure.md`, and acs-readiness tooling, then
ADDITIVELY scaffold only what is missing as one reviewed PR — you never move, rename,
delete, or rewrite existing source. This is the brownfield counterpart to the
greenfield-only `/acs:create-project`; it is a dedicated triad-keeping workflow skill,
not a `<set>_path` doc-set producer (D5 Option B). You orchestrate subagents; you never
scaffold anything yourself.

## Start

MANDATORY first action — run exactly one of:

- Fresh run (the normal case; each run gets its own delivery ticket):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/skill-start.py" --skill standardize-project --allocate --args "$ARGUMENTS"
```

- Resume: if `$ARGUMENTS` contains an existing delivery-ticket id (e.g. `SHOP-9` from a
  handoff `continue_with` command), do NOT allocate — rejoin that partition:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/skill-start.py" --skill standardize-project --ticket SHOP-9
```

If skill-start exits non-zero: stop immediately and surface its stderr to the user
verbatim — do not improvise. Otherwise parse the printed context JSON; the fields you
need: `partition`, `ticket_id`, `ticket`, `settings` (`principles_path`,
`standards_path`, `architecture_path`, `test_coverage_percent`, `e2e`, `formats`,
`tracker`), `models`, `reconcile`, `handoff_summary`, `post_hook`, `pipeline`,
`checkout_root`.

The allocated delivery ticket is type `task`, titled **"Brownfield project standardization"**
(`DELIVERY_TICKET_TITLES`); skill-start has already created the
partition, ticket.json, the lock, the session pointer, and the `in_progress` run entry.
If `settings.tracker.provider` is `github` or `jira`, sync the ticket out via `gh`/`acli`
per the tracker config.

**No refusal guard on this skill's own set.** Unlike every product-level producer
(`create-standards/SKILL.md:45-48`, keyed to `standards_path == null`),
`standardize-project` has no `<set>_path` of its own to be null: it is not a doc-set
producer. The Start phase never blocks on `principles_path` or `standards_path` — the
audit always proceeds (see Brownfield orientation below); a missing or unset doc set is
a grounding-input condition handled in Inputs & mode, not a Start-time concern.

If `settings.models.coordinator` is set and this is a direct invocation (not under
`/acs:ship`), state in one line that it governs the ship coordinator's own session, not
this directly typed invocation — never silently diverge.

## Resume & reconcile

If `context.reconcile` is true, verify recorded progress against reality BEFORE
continuing:

- Read `<partition>/phases/standardize-project/` — the persisted `iter-<n>-<phase>.xml`
  files tell you the last completed phase and iteration.
- Re-read the actual artifacts: which files under `<checkout_root>` were scaffolded per
  the last recorded plan; whether the ticket branch exists (`git branch --list`), is
  committed, pushed, or already has a PR (`gh pr list --head <branch>`).
- Distrust the record where it is cheap to re-check.
- Continue from the first unfinished phase of the recorded iteration.

If `context.handoff_summary` exists, read it plus
`<partition>/phases/standardize-project/handoff-context.md` (if present), do a light
reconcile, and continue from where it points.

## Brownfield orientation

Unlike `/acs:create-project` (`create-project/SKILL.md:70-94`), this skill does NOT scan
for and refuse on existing sources — the presence of substantive source is the expected,
normal case this skill operates on. There is no greenfield-style refusal path here:
`standardize-project` assumes an EXISTING repo with substantive sources and never
refuses on their presence — auditing them is its entire purpose.

This is a dedicated triad rather than a fold into `create-project` because the
additive-only guardrail (D6) needs its own independent verifier, which an inline
extension of `create-project` could not host (D5 Option C's rejection,
`design.md:265-274`).

## Inputs & mode

The audit inputs, read before spawning the planner:

- `<architecture_path>/hld/project-structure.md` — the structural target (D4, MAR-120's
  `/acs:create-architecture` output). **May not exist** on a given consumer repo. When
  absent, note it explicitly as N/A for the structural-gap dimension and surface "run
  `/acs:create-architecture`" as a `recommended_follow_ups` entry — never a block, never
  invoked inline (mirrors the graceful-degradation NFR, `prd.md:611-616`).
- `<principles_path>/` and `<standards_path>/` — read WHEN each is set (non-null) AND a
  doc set actually exists at that path. **Graceful degradation (mandatory):** when a
  path is `null`, OR set but no doc set exists there yet, note this explicitly in the
  plan's audit inventory as N/A and PROCEED — this grounding step is N/A for this run,
  never a hard block. A missing/absent set surfaces as a `recommended_follow_ups` entry
  ("run `/acs:create-principles`" / "run `/acs:create-standards`") — see
  Additive-surface contract below for why this skill never authors that content itself.
- **acs-readiness tooling** — four checks, each independently gradeable
  present/absent/n/a, never gating the others:
  - CI workflow presence (e.g. a workflow file under `.github/workflows/` or the repo's
    equivalent CI config location).
  - pre-commit config presence (e.g. `.pre-commit-config.yaml` or the stack's
    equivalent).
  - coverage-tool config presence AND whether it fails the run below
    `settings.test_coverage_percent`.
  - e2e harness/config presence relative to `settings.e2e` — **when `settings.e2e` is
    unset, this whole dimension is N/A** (the opt-in invariant: unset = no e2e suite, no
    gate).

  When the repo's existing build/test/CI tooling is genuinely ambiguous (no package
  manifest, or multiple candidate stacks/CI providers), the planner surfaces this as an
  open question rather than guessing.

**No bootstrap/re-run mode split.** Unlike the doc-set producers, `standardize-project`
has no `bootstrap` vs `re-run` distinction on its own output — there is no fixed doc set
it owns. Every run performs a fresh audit of current repo state and scaffolds whatever
remains missing; this is naturally idempotent because the executor only ever adds (never
rewrites) — a second run against an already-standardized repo finds nothing left to
scaffold and reports zero gaps.

## Additive-surface contract

Unlike the fixed-file-set producers (`create-standards`' exactly 3 files,
`create-principles`' exactly 1), `standardize-project`'s scaffold surface is VARIABLE per
audited repo — computed fresh by the planner's audit, not a static table. This section
pins the FIXED parts of the contract: the allowlist CATEGORIES the planner may draw from
(never the literal path list, which varies per run) and the `recommended_follow_ups`
shape.

**Additive-surface allowlist categories.** The planner emits, and the verifier enforces
every iteration (via spec 01's `classify_additive_diff` helper), an allowlist drawn ONLY
from:

1. New CI workflow file(s) the executor adds (e.g. under `.github/workflows/`) — `A`
   (added) status only.
2. New or additively-appended tooling config the skill itself owns and the plan names
   explicitly — coverage-tool config, pre-commit config, e2e runner scaffold config. `A`
   (new file) is always allowed; `M` (modify, an additive append such as a new
   key/hook/script) is allowed ONLY for the specific paths the plan names as append
   targets — every path NOT named this way defaults to requiring `A`.
3. The delivery branch/commit/PR metadata itself is governed by `pr-conventions.py` and
   the Delivery section below, not by this file-diff allowlist — it is not a path in the
   `git diff --name-status` output.

Everything else the executor's diff touches must be `A` status (a wholly new file) —
never `R`, `D`, or an `M` outside the two categories above.

**Deviation from the design's broader allowlist — resolved report-only.** The design's
own allowlist text additionally lists `<principles_path>/**` and `<standards_path>/**`
(new files only, or invoking the producer skill) as scaffold-able categories. This spec
DROPS both from the executor's allowlist entirely — the executor NEVER writes into
`<principles_path>/**` or `<standards_path>/**`, under either mechanism: it cannot
invoke a producer skill inline (subagents never spawn subagents; the executor's
`disallowedTools: Agent, Skill`), and it does not author doc-set content directly either
(ADR 0011's one-skill-per-set invariant). A missing/absent `principles/` or `standards/`
doc set is therefore ALWAYS a `recommended_follow_ups` entry — never an executor
scaffold target.

**`recommended_follow_ups` shape** — an array of objects, ALWAYS present on the result
document (empty array when no structural gaps found):

| Key | Content |
|---|---|
| `title` | short imperative summary, e.g. "Bootstrap the standards/ doc set" |
| `rationale` | why this gap matters — the audit finding it traces to |
| `target_path` | the repo-relative path or skill invocation this follow-up targets, e.g. `docs/standards/` or `/acs:create-standards` |

A `recommended_follow_ups` entry is NEVER auto-minted as a ticket by this skill (D7
Option A / C-5) — the user decides whether to act on it. This covers both doc-set gaps
AND structural gaps versus `hld/project-structure.md` (AC-6) — both categories flow
through this same one array, never a second output channel.

## Reflection loop

Mirrors `create-standards/SKILL.md:130-213` in structure: plan → execute → verify, max 3
iterations. Spawn subagents via the Agent tool: `subagent_type`
`acs:standardize-project-planner` / `acs:standardize-project-executor` /
`acs:standardize-project-verifier` (fall back to the un-namespaced name if the runtime
rejects the namespaced one). Apply `context.models.<role>.model`/`.effort` at spawn when
not `"inherit"`; fail the run (no silent fallback) if the runtime rejects the
model/effort. Communicate in XML per `schemas/acs-messages.xsd`; validate every message
via `validate_xml.py`; on an invalid message, re-request once, then fail with the
validation error recorded in `errors`. Persist every phase output to
`<partition>/phases/standardize-project/iter-<n>-<phase>.xml` before starting the next
phase.

Example plan task (illustrates the audit-inputs contract and the narrowed allowlist
together):

```xml
<task skill="standardize-project" phase="plan" ticket-id="SHOP-9" iteration="1">
  <objective>Audit this repo against principles_path, standards_path, hld/project-structure.md, and acs-readiness tooling; produce a gap list, an additive-surface allowlist scoped to CI/tooling config only, and structural-gap candidates as recommended follow-ups.</objective>
  <inputs>
    <file>docs/architecture/hld/project-structure.md</file>
    <file>docs/principles/</file>
    <file>docs/standards/</file>
    <file>.github/workflows/</file>
    <file>.pre-commit-config.yaml</file>
  </inputs>
  <constraints>
    <constraint name="coverage-target">90</constraint>
    <constraint name="read-only">The plan phase mutates nothing.</constraint>
    <constraint name="no-doc-set-authorship">principles_path/standards_path content is never a scaffold target — a missing set is always a recommended_follow_ups entry, never authored or invoked inline.</constraint>
    <constraint name="e2e-opt-in">settings.e2e unset means the e2e readiness dimension is N/A — no e2e scaffold, no gate.</constraint>
  </constraints>
</task>
```

Phases:

1. **Plan** — the planner AUDITS (read-only): reads the doc-set/target/readiness-tooling
   inputs above, produces a gap list classified into scaffold-able (CI/tooling config)
   vs recommended-follow-up-only (missing doc sets, missing `hld/project-structure.md`,
   structural gaps against it), the additive-surface allowlist the verifier will
   enforce, and the `recommended_follow_ups` candidates. Persist the plan.
2. **Execute** — the executor writes ONLY the allowlisted new files and named additive
   config appends — never edits, renames, or deletes any pre-existing source file, and
   never writes under `<principles_path>/**` or `<standards_path>/**`. Decomposition is
   the coordinator's alone; subagents never spawn subagents.
3. **Verify** — after all executors finish, spawn the verifier on the combined result.
   It judges fresh from artifacts only — never the executors' reasoning — and re-runs,
   itself, EVERY iteration (never reusing a prior iteration's result, never trusting the
   execute report's `files_changed` list as a substitute):

```bash
git -C <checkout_root> diff --name-status <default_branch>...HEAD
```

   passing that raw output plus the planner's allowlist entries to spec 01's
   `classify_additive_diff` helper in `acs_lib.py`. Every returned violation — any `R`,
   any `D`, any out-of-allowlist `M` — becomes `severity="blocking"
   dimension="additive-only"`, citing the exact path and status. The verifier's full
   check-dimension list (additive-only diff-status, doc-set-authorship boundary,
   recommended-follow-ups-only, plan-conformance, completion-report shape) is defined in
   its own agent prose (`standardize-project-verifier.md`) and re-run every iteration.

Zero verifier findings = pass — proceed to Delivery. On findings, feed them verbatim
into the next iteration's plan task and re-run plan → execute → verify. After iteration
3 with findings remaining: stop, final status `failed`, findings recorded in the result
document; commit whatever was written to the local ticket branch so nothing is lost, but
do NOT push or open the PR.

## Delivery

Mirrors `create-standards/SKILL.md:215-277` in structure — the delivery-ticket pattern,
done by the coordinator itself:

1. **Branch** (before the first executor writes, so the verifier's `git diff
   --name-status <default_branch>...HEAD` has a meaningful base): require a clean
   working tree; render `settings.formats.branch_name` with `type=task`, the ticket id,
   and the slugified title (e.g. `task/SHOP-9-brownfield-project-standardization`);
   `git checkout -b` from the default branch.
2. **Commit** (after the verifier passes): stage exactly the files the verifier's final
   passing diff-status check confirmed (never a broader `git add -A` that could sweep up
   something outside the allowlist); commit with `settings.formats.commit_message` (e.g.
   `SHOP-9 Additively scaffold missing docs/config/tooling`).
3. **Push & PR**: `git push -u origin <branch>`; render the PR title via the helper —
   NOT LLM prose composition — capturing its stdout:

```bash
gh label create ACS --description "Created by the acs pipeline" 2>/dev/null || true
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pr-conventions.py" render-title \
  --template "<settings.formats.pr_title>" --ticket-id <ticket_id> --type task \
  --title "Brownfield project standardization" --summary "<summary>" --external-key "<ticket.external.key or empty>" \
  --provider "<ticket.external.provider or empty>"
```

   The body comes from `settings.formats.pr_description_template`. Fill its placeholders
   from `ticket.json` and the verifier result — never from conversation memory. **After
   filling the standard template placeholders, append a `## Recommended follow-ups`
   section** listing every `recommended_follow_ups` entry as a bullet (`- **<title>**:
   <rationale> (target: <target_path>)`), or the single line "None — no structural or
   doc-set gaps found" when the array is empty. This is an ADDITIONAL section appended
   to the rendered body, not a new global template placeholder.

   **Pre-open self-check** via `pr-conventions.py check` before `gh pr create`; on
   failure, bounded local re-render/re-check (up to 2 attempts); if still failing, STOP
   — do not call `gh pr create` — surface the blocking finding.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pr-conventions.py" check \
  --title "<rendered title>" --body-file <body.md> --require-label ACS \
  --pr-title-format "<settings.formats.pr_title>" \
  --sections "<settings.enforcement.pr_description_sections, comma-joined>" \
  --ticket-prefix <settings.ticket_prefix>
```

   On pass, `gh pr create --base <default-branch> --head <branch> --title "<rendered
   title>" --body-file <body.md> --label ACS`.
4. Record `{number, url, branch}` for the result document. The post-hook moves the
   delivery ticket to `in_review`; `/acs:merge-pr` lands it like any other ticket.
   Exactly ONE PR per run — a structural gap NEVER triggers a second PR or an
   auto-mint, it only adds an entry to `recommended_follow_ups`.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list --ticket <ticket-id>`
and reuse any recorded answer — re-asking an answered question is a defect. When ≥2
clarifications are open, present them to the user in ONE grouped interaction, not serial
round-trips. Record each answer as its own `clarify.py add` entry (one `C-<n>` per
question, `--source` preserved). Never skip a question, merge two questions into one
entry, or auto-answer a question outside the existing `--source assumption --rationale
"..."` rule.
Record every Q&A with `clarify.py add --skill standardize-project --question "..."
--answer "..." --ticket <ticket-id>` BEFORE acting on it, and pass the relevant `C-n`
entries to subagents in `<context>`. If the user is unavailable, record the decision
with `--source assumption --rationale "..."`. Before a needs_input handoff, record
outgoing questions as `open`.
Ask clarifying questions when genuinely ambiguous — at minimum, any ambiguity the
planner surfaces about the repo's build/CI/test tooling (see Inputs & mode); do not ask
about anything the repo's own config already answers. If genuinely unreachable, return a
`<handoff skill="standardize-project" ticket-id="<id>" status="needs_input">` with
`<questions>` instead of guessing.

## Context pressure

If your context is running low mid-run: flush in-flight work plus soft context to
`<partition>/phases/standardize-project/handoff-context.md`, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --ticket <id> --summary "<done / in-flight / next / decisions>"
```

Tell the user the printed `continue_with` command.

## Finish

MANDATORY final step — never skipped, also on failure:

1. Write `<partition>/phases/standardize-project/result.json` per the result-document
   contract in INTERNALS.md (`docs/architecture/lld/contracts.md:27`). Canonical
   `states` keys: `audit`, `scaffold`, `pr` — plus the top-level `recommended_follow_ups`
   array (ALWAYS present, empty when there is nothing to recommend):

```json
{
  "status": "completed",
  "stop_reason": "audit complete; additive scaffold verified additive-only; PR opened with recommended follow-ups listed",
  "states": {
    "audit": {
      "principles": "absent",
      "standards": "present",
      "project_structure": "present",
      "readiness_tooling": {"ci": false, "pre_commit": true, "coverage": true, "e2e": "n/a"}
    },
    "scaffold": {"files_added": [".github/workflows/ci.yml"]},
    "pr": {"number": 14, "url": "https://github.com/owner/repo/pull/14", "branch": "task/SHOP-9-brownfield-project-standardization"}
  },
  "recommended_follow_ups": [
    {"title": "Bootstrap the principles/ doc set", "rationale": "principles_path is set to docs/principles but no doc set exists there yet", "target_path": "/acs:create-principles"}
  ],
  "findings": [],
  "errors": [],
  "tokens": {"input": 0, "output": 0},
  "cost_usd": 0.0
}
```

   `states.audit.*` values for `principles`/`standards`/`project_structure` are one of
   `"present" | "absent" | "n/a"` (`"n/a"` when the corresponding `<set>_path` setting is
   unset); `readiness_tooling.e2e` is boolean OR the literal string `"n/a"` when
   `settings.e2e` is unset. On failure: `status: "failed"`, blocking findings in
   `findings`, reason in `stop_reason`, keep whatever is true in `states`,
   `recommended_follow_ups` still reflects whatever the last passing plan found. On
   handoff: `status: "handed_off"` plus `handoff_summary`.
2. Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-standardize-project.py" --ticket <id> --result-file <partition>/phases/standardize-project/result.json
```

3. Report a compact summary to the user: audit findings, files scaffolded, verifier
   iterations, PR URL, the `recommended_follow_ups` list, and that `/acs:merge-pr` lands
   it after review. If genuinely unreachable, return ONLY the `<handoff>` XML.

## Completion report (normative)

Every terminal outcome of a direct invocation ends the final message with the standard
block (INTERNALS.md "Completion report"), rendered only after the post-hook succeeded,
same labels/order, `none` where empty; under `/acs:ship` the final message is the
`<handoff>` XML instead:

```markdown
## /acs:standardize-project · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <stop_reason>
- **Results**: audit summary (doc sets / project-structure / readiness tooling); files additively scaffolded; delivery ticket id; PR number/URL
- **Findings**: <open findings / clarifications, or "none">
- **Recommended follow-ups**: <recommended_follow_ups titles, or "none">
- **Artifacts**: <partition files, repo paths, branch, PR URL>
- **Metrics**: iterations <n>/3 · <wall time> · ~<tokens in/out> · ~$<cost_usd>
- **Next**: `/acs:merge-pr <ticket-id>` after reviewing the scaffold PR; consider the recommended follow-ups
```
