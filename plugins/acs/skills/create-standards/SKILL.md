---
name: create-standards
description: Bootstrap or maintain the consumer standards/ doc set (coding standards, naming/layout/formatting conventions, review checklist) from templates, reading the PRD, the architecture/ set, and the principles/ set (when present) as upstream, delivered as a docs-only PR on its own delivery ticket. Use after /acs:create-principles, or to refresh the standards doc set after a coding-standard or convention change.
argument-hint: "[delivery-ticket-id to resume | focus notes]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-standards. You produce or maintain the consumer
`standards/` doc set (coding standards & conventions) in the consumer repo at
`settings.standards_path` (default `docs/standards`), grounded against the PRD, the
`architecture/` set, and the `principles/` set (when present), and ship it as a docs-only
PR on a fresh delivery ticket. This is a product-level skill: it is ticket-independent. You
orchestrate subagents; you never write the standards docs yourself.

## Start

MANDATORY first action — run exactly one of:

- Fresh run (the normal case; each run gets its own delivery ticket):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/skill-start.py" --skill create-standards --allocate --args "$ARGUMENTS"
```

- Resume: if `$ARGUMENTS` contains an existing delivery-ticket id (e.g.
  `SHOP-4` from a handoff `continue_with` command), do NOT allocate — rejoin
  that partition:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/skill-start.py" --skill create-standards --ticket SHOP-4
```

If skill-start exits non-zero: stop immediately and surface its stderr to the
user verbatim. Otherwise parse the printed context JSON; the fields you need:
`partition`, `ticket_id`, `ticket`, `settings` (`prd_path`, `architecture_path`,
`principles_path`, `standards_path`, `formats`, `tracker`), `models`, `reconcile`,
`handoff_summary`, `post_hook`, `pipeline`, `checkout_root`.

The allocated delivery ticket is type `task`, titled `Product standards doc set`
(`PRODUCT_TICKET_TITLES`); skill-start has already created the partition,
ticket.json, the lock, the session pointer, and the `in_progress` run entry.
If `settings.tracker.provider` is `github` or `jira`, sync the ticket out via
`gh`/`acli` per the tracker config.

**The refusal guard is keyed EXCLUSIVELY to this skill's own set.** If
`settings.standards_path` is `null`: STOP before allocating further work — the
consumer has explicitly opted out of acs maintaining this doc set (mirrors
`adr_path`'s unset-disables convention). Surface this to the user and do not run.

Do NOT refuse or stop when `settings.principles_path` is `null`, or when
`principles_path` is set but no `principles/` doc set exists there yet —
`principles/` is an upstream grounding *input* for `create-standards` (D1), not
this skill's own output set; a missing/absent principles set only makes that one
grounding step N/A in the plan (see Inputs & mode below) and the run proceeds —
never a Start-time block. This is the deliberate inversion of
`create-principles/SKILL.md`'s Start guard, which is keyed to `principles_path`
because that is *its own* set.

If `settings.models.coordinator` is set and this is a DIRECT invocation (a
user typed `/acs:create-standards`, not driven under /acs:ship), tell the
user in one line that `models.coordinator` governs the ship coordinator's own
run under /acs:ship, not a directly typed skill — never silently diverge.

## Resume & reconcile

If `context.reconcile` is true, verify recorded progress against reality
BEFORE continuing:

- Read `<partition>/phases/create-standards/` — the persisted
  `iter-<n>-<phase>.xml` files tell you the last completed phase and
  iteration.
- Re-read the actual artifacts: which files under `<checkout_root>/<standards_path>/`
  exist and are complete; whether the ticket branch exists (`git branch --list`), is
  committed, pushed, or already has a PR (`gh pr list --head <branch>`).
- Distrust the record where it is cheap to re-check (a doc "written" but
  missing or truncated counts as not done).
- Continue from the first unfinished phase of the recorded iteration.

If `context.handoff_summary` exists, read it plus
`<partition>/phases/create-standards/handoff-context.md` (if present),
do a light reconcile (spot-check the claimed artifacts), and continue from
where the summary points.

## Inputs & mode

The upstream inputs are `<prd_path>/prd.md`, the full `<architecture_path>/` set, AND
`<principles_path>/` — read the `principles/` set **when `settings.principles_path` is
set (non-null) AND a `principles/` doc set actually exists at that path**. This is the
*inverse* of `create-principles/SKILL.md`, which explicitly has NO cross-read on
`standards/` or any downstream doc set — `create-standards` is the one skill in the pair
with the extra upstream read: the conformance chain is `architecture → principles →
standards`, an altitude gradient where an abstract principle is realized by a concrete
standard.

**Graceful degradation (mandatory):** when `settings.principles_path` is `null`, OR it is
set but no `principles/` doc set exists there yet (e.g. `create-principles` has not
bootstrapped it on this repo), note this explicitly and PROCEED — this grounding step is
N/A for this run, never a hard block. Tailor the output from PRD + architecture alone in
that case. Do not copy a refusal condition keyed to `principles_path` into this skill —
the ONLY refusal condition is the Start-time `standards_path == null` check above, on
this skill's own set.

Read `prd.md`, the architecture set, and (when applicable) the principles set before
spawning the planner. Mode is a simple two-way split, keyed to `standards_path` only
(principles-availability is an orthogonal axis — it never gates doc-set mode):

- **bootstrap** — no `standards/` doc set exists yet at `standards_path`.
- **re-run/amend** — the doc set exists at `standards_path` — regenerate/tailor in
  place, preserving still-accurate content.

## Output contract

The executor writes EXACTLY these three files, bootstrapped from the templates into
`<checkout_root>/<standards_path>/` (no other repo files are touched):

| File | Content |
|------|---------|
| `coding-standards.md` | language/framework-level coding standards — error handling, testing conventions, API-design idioms |
| `conventions.md` | naming, file/directory layout, and formatting conventions |
| `review-checklist.md` | code-review checklist derived from the coding standards and conventions above |

The executor bootstraps each file from its `plugins/acs/templates/standards/` template
verbatim, then lightly tailors it to the consumer's detected stack (read from the
`architecture/` set) and, when available, to the stated principles (read from the
`principles/` set) — the same bootstrap-then-tailor shape `create-quality`/
`create-operations`/`create-principles` use. No living-parts ledger — these files
document durable standards and conventions, not a running log. Exactly 3 files, never a
4th.

## Reflection loop

Run plan -> execute -> verify, max 3 iterations.

Spawn subagents with the Agent tool: subagent_type
`acs:create-standards-planner` / `acs:create-standards-executor` /
`acs:create-standards-verifier` (fall back to the un-namespaced name if
the runtime rejects the namespaced one). Apply
`context.models.<role>.model` / `.effort` at spawn when not `"inherit"`; if
the runtime rejects the model or effort, FAIL the run with that error — no
silent fallback.

Communicate in XML per `schemas/acs-messages.xsd`. Example plan task:

```xml
<task skill="create-standards" phase="plan" ticket-id="SHOP-4" iteration="1">
  <objective>Read the PRD, the architecture set, and the principles/ set when present; decide bootstrap vs re-run; produce a file-by-file plan for the standards/ doc set, tailored to the detected stack and (when available) the stated principles.</objective>
  <inputs>
    <file>docs/product/prd.md</file>
    <file>docs/architecture/</file>
    <file>docs/principles/</file>
    <file>docs/standards/</file>
  </inputs>
  <constraints>
    <constraint name="output-files">coding-standards.md, conventions.md, review-checklist.md only — no other file</constraint>
    <constraint name="read-only">The plan phase mutates nothing.</constraint>
    <constraint name="principles-optional">principles_path may be null, or the principles/ set may be absent — treat as grounding N/A for this iteration, never a block.</constraint>
  </constraints>
</task>
```

Validate EVERY message you send and receive:

```bash
echo "<xml>" | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/validate_xml.py" -
```

On an invalid message, re-request it once; if still invalid, fail the run
with the validation error recorded in `errors`.

Persist every phase output to
`<partition>/phases/create-standards/iter-<n>-<phase>.xml` at the phase
boundary, BEFORE starting the next phase.

Phases:

1. **Plan** — the planner reads the upstream doc-graph slice (PRD + architecture set +
   principles set when present), notes any gaps as `<questions>`, classifies bootstrap vs
   re-run, and produces the per-file outline for the 3 `standards/` files. The planner
   also runs the shared ADR-0012 design-time doc-consistency step; any findings surface
   through the "Clarification ledger first" mechanism below (User interaction). Persist
   the plan.
2. **Execute** — executor(s) write the 3 files on the ticket branch (create
   the branch first — see Delivery). Decomposition is YOURS alone; subagents
   never spawn subagents. Typically a single executor — three small, tightly coupled
   files.
3. **Verify** — after ALL executors finish, spawn the verifier on the
   combined result. It judges fresh from artifacts only (never the
   executors' reasoning) and checks, all blocking:
   - all three planned files exist, no unplanned extra file;
   - the tailored content **conforms to the architecture set** (no invented
     stack/technology claim not present in `architecture/hld/tech-stack.md` and the
     rest of the set);
   - required sections are present in each file;
   - the plan was followed exactly;
   - the changeset is docs-only;
   - **consistency**: any `consistency_findings` the planner surfaced (the
     shared ADR-0012 design-time doc-consistency step, see Plan above) were
     resolved or explicitly user-deferred in the clarification ledger.

   **This producer verifier stays a mirror of the `create-principles` producer
   verifier** — it checks ONLY `create-standards`' own doc set (the six dimensions
   above). It does NOT add a seventh "each standard traces to a stated principle"
   blocking sub-check in this child: `principles/` is read as a grounding input to
   tailor content, never as a second doc set this verifier cross-checks conformance
   against — that pipeline-wide standards-conformance dimension belongs to a future
   mechanism, not this producer skill's own verifier.

Zero verifier findings = pass — proceed to Delivery. On findings, feed them
verbatim into the next iteration's plan task and re-run
plan -> execute -> verify. After iteration 3 with findings remaining: stop,
final status `failed`, findings recorded in the result document; commit
whatever was written to the local ticket branch so nothing is lost, but do
NOT push or open the PR.

## Delivery (branch, commit, PR)

The delivery-ticket pattern (same as /acs:create-architecture — you do this yourself;
/acs:create-design, /acs:create-spec, and /acs:code are not involved):

1. **Branch** (before the first executor writes): require a clean working
   tree (`git status --porcelain` empty — if not, ask the user before
   proceeding). Render `settings.formats.branch_name` (default
   `{type}/{ticket_id}-{slug}`) with `type=task`, the ticket id, and the
   slugified title — e.g. `task/SHOP-4-product-standards-doc-set` — and
   `git checkout -b` it from the default branch.
2. **Commit** (after the verifier passes): stage ONLY
   `<standards_path>/` and verify the diff is docs-only
   (`git diff --cached --name-only` — every path under
   `standards_path`). Commit with `settings.formats.commit_message`
   (default `{ticket_id} {summary}`), e.g.
   `SHOP-4 Add product standards doc set` (or `Regenerate …` on re-run).
3. **Push & PR**: `git push -u origin <branch>`, then render the title via the
   helper — NOT LLM prose composition — capturing its stdout as
   `<rendered title>`:

```bash
gh label create ACS --description "Created by the acs pipeline" 2>/dev/null || true
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pr-conventions.py" render-title \
  --template "<settings.formats.pr_title>" --ticket-id <ticket_id> --type <ticket.type> \
  --title "<delivery ticket's title>" --summary "<summary>" --external-key "<ticket.external.key or empty>" \
  --provider "<ticket.external.provider or empty>"
```

   The title renders `settings.formats.pr_title` (default
   `[{ticket_id}] {title}`). The body comes from
   `settings.formats.pr_description_template`: built-in name `pr-default` ->
   `${CLAUDE_PLUGIN_ROOT}/templates/pr-default.md`; otherwise
   `<checkout_root>/.acs/templates/<name>.md`; otherwise an absolute path.
   Fill its placeholders from `ticket.json` and the verifier result — never
   from conversation memory.

   **Pre-open self-check** — before `gh pr create`, self-check the rendered
   title and filled body with the helper's `check` subcommand (a
   deterministic CLI call, never a spawned subagent):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pr-conventions.py" check \
  --title "<rendered title>" --body-file <body.md> --require-label ACS \
  --pr-title-format "<settings.formats.pr_title>" \
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
gh pr create --base <default-branch> --head <branch> --title "<rendered title>" --body-file <body.md> --label ACS
```

4. Record `{number, url, branch}` for the result document. The post-hook
   moves the delivery ticket to `in_review`; /acs:merge-pr later lands it
   like any other ticket.

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
`clarify.py add --skill create-standards --question "..." --answer "..." --ticket <ticket-id>`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`. If the user is unavailable or says "you decide": record the
decision with `--source assumption --rationale "..."` — assumptions surface
in the completion report's Findings and the PR body until a user confirms.
Before a needs_input handoff, record the outgoing questions as `open`
(`clarify.py add` without `--answer`).

Ask clarifying questions when genuinely ambiguous (AskUserQuestion or plain
questions) — at minimum: any gap between the PRD, the architecture set, and (when
present) the principles set the planner surfaces. Do not ask about things the PRD, the
architecture set, or the principles set already answer.

If you genuinely cannot reach the user (e.g. a non-interactive run), do not
guess — return a `<handoff skill="create-standards" ticket-id="<id>"
status="needs_input">` with the `<questions>` list instead.

## Context pressure

If your context is running low mid-run: flush in-flight work plus soft
context (mode decision, partial verifier findings, gotchas) to
`<partition>/phases/create-standards/handoff-context.md`, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --ticket <id> --summary "<done / in-flight / next / decisions>"
```

Tell the user the `continue_with` command it prints (re-running this skill
with the delivery-ticket id resumes via the Start section's resume form).

## Finish

MANDATORY final step — never skipped, also on failure:

1. Write `<partition>/phases/create-standards/result.json` per the
   result-document contract in INTERNALS.md. Canonical `states` keys (exact
   names): `standards` and `pr`. `files` entries are paths relative to `<path>/`:

```json
{
  "status": "completed",
  "stop_reason": "doc set verified against the architecture set; docs-only PR opened",
  "states": {
    "standards": {
      "path": "docs/standards",
      "files": ["coding-standards.md", "conventions.md", "review-checklist.md"]
    },
    "pr": {"number": 10, "url": "https://github.com/owner/repo/pull/10", "branch": "task/SHOP-4-product-standards-doc-set"}
  },
  "findings": [],
  "errors": [],
  "tokens": {"input": 0, "output": 0},
  "cost_usd": 0.0
}
```

   Fill `tokens`/`cost_usd` with your best estimate for this run. On
   failure: `status: "failed"`, the blocking findings in `findings`, the
   reason in `stop_reason`, keep whatever is true in `states` (e.g. the
   written `standards` files without `pr`). On handoff:
   `status: "handed_off"` plus `handoff_summary`.

2. Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-standards.py" --ticket <id> --result-file <partition>/phases/create-standards/result.json
```

3. Report a compact summary to the user: mode, files written, verifier
   iterations, PR URL, and that /acs:merge-pr (after their review) lands it.
   If you genuinely cannot reach the user (a non-interactive run), return ONLY the
   `<handoff>` XML as your final message: status, summary under 1 KB,
   artifact refs (doc-set path, result.json, PR URL), and `<next-step>`.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty; under /acs:ship your final message is the `<handoff>` XML instead — this report is for direct invocations:

```markdown
## /acs:create-standards · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <stop_reason>
- **Results**: standards/ files written at `standards_path`; delivery ticket id; PR number/URL
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <partition files, repo paths, branch, PR URL>
- **Metrics**: iterations <n>/3 · <wall time> · ~<tokens in/out> · ~$<cost_usd>
- **Next**: `/acs:merge-pr <ticket-id>` after reviewing the docs PR
```
