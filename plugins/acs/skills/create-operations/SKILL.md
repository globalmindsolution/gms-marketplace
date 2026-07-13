---
name: create-operations
description: Bootstrap or maintain the consumer operations/ doc set (release process, runbooks, observability, incident response, test-scheduling recipe) from templates, reading the PRD non-functional requirements and the architecture/ set as upstream, delivered as a docs-only PR on its own delivery ticket. Use after /acs:create-architecture (or alongside /acs:create-quality), or to refresh the operations doc set after a release-process or on-call change.
argument-hint: "[delivery-ticket-id to resume | focus notes]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-operations. You produce or maintain the consumer
`operations/` doc set (release process, runbooks, observability, incident response,
test-scheduling recipe) in the consumer repo at `settings.operations_path` (default
`docs/operations`), verified against the PRD's non-functional requirements and the
`architecture/` set, and ship it as a docs-only PR on a fresh delivery ticket. This is a
product-level skill: it is ticket-independent. You orchestrate subagents; you never write
the operations docs yourself.

## Start

MANDATORY first action — run exactly one of:

- Fresh run (the normal case; each run gets its own delivery ticket):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/skill-start.py" --skill create-operations --allocate --args "$ARGUMENTS"
```

- Resume: if `$ARGUMENTS` contains an existing delivery-ticket id (e.g.
  `SHOP-2` from a handoff `continue_with` command), do NOT allocate — rejoin
  that partition:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/skill-start.py" --skill create-operations --ticket SHOP-2
```

If skill-start exits non-zero: stop immediately and surface its stderr to the
user verbatim. Otherwise parse the printed context JSON; the fields you need:
`partition`, `ticket_id`, `ticket`, `settings` (`prd_path`, `architecture_path`,
`operations_path`, `formats`, `tracker`), `models`, `reconcile`, `handoff_summary`,
`post_hook`, `pipeline`, `checkout_root`.

The allocated delivery ticket is type `task`, titled `Product operations doc set`
(`PRODUCT_TICKET_TITLES`); skill-start has already created the partition,
ticket.json, the lock, the session pointer, and the `in_progress` run entry.
If `settings.tracker.provider` is `github` or `jira`, sync the ticket out via
`gh`/`acli` per the tracker config.

If `settings.operations_path` is `null`: STOP before allocating further work — the
consumer has explicitly opted out of acs maintaining this doc set (mirrors
`adr_path`'s unset-disables convention). Surface this to the user and do not run.

If `settings.models.coordinator` is set and this is a DIRECT invocation (a
user typed `/acs:create-operations`, not driven under /acs:ship), tell the
user in one line that `models.coordinator` governs the ship coordinator's own
run under /acs:ship, not a directly typed skill — never silently diverge.

## Resume & reconcile

If `context.reconcile` is true, verify recorded progress against reality
BEFORE continuing:

- Read `<partition>/phases/create-operations/` — the persisted
  `iter-<n>-<phase>.xml` files tell you the last completed phase and
  iteration.
- Re-read the actual artifacts: which files under `<checkout_root>/<operations_path>/`
  exist and are complete; whether the ticket branch exists (`git branch --list`), is
  committed, pushed, or already has a PR (`gh pr list --head <branch>`).
- Distrust the record where it is cheap to re-check (a doc "written" but
  missing or truncated counts as not done).
- Continue from the first unfinished phase of the recorded iteration.

If `context.handoff_summary` exists, read it plus
`<partition>/phases/create-operations/handoff-context.md` (if present),
do a light reconcile (spot-check the claimed artifacts), and continue from
where the summary points.

## Inputs & mode

The upstream inputs are `<prd_path>/prd.md` (its Non-functional requirements section
specifically) and the full `<architecture_path>/` set (architecture is upstream of
operations). Read both before spawning the planner. Mode is a simple two-way split:

- **bootstrap** — no `operations/` doc set exists yet at `operations_path`.
- **re-run/amend** — the doc set exists at `operations_path` — regenerate/tailor in
  place, preserving still-accurate content.

## Output contract

The executor writes EXACTLY these five files, bootstrapped from the templates into
`<checkout_root>/<operations_path>/` (no other repo files are touched):

| File | Content |
|------|---------|
| `release-process.md` | release cadence, versioning scheme, cut/rollback procedure |
| `runbooks.md` | operational runbook index, on-call procedures |
| `observability.md` | logging/metrics/tracing/dashboard conventions |
| `incident-response.md` | severity levels, triage/escalation process, postmortem process (no ledger) |
| `test-scheduling.md` | recurring test/eval invocation recipe (generic — no `suites`-schema coupling) |

The executor bootstraps each file from its `plugins/acs/templates/operations/` template
verbatim, then lightly tailors it to the consumer's detected stack/deployment (read from
the `architecture/` set) — the same bootstrap-then-tailor shape `/acs:create-project` uses
for its scaffold templates. Living parts (e.g. a postmortem ledger) are explicitly out of
scope — `incident-response.md` documents the postmortem *process*, not a running log.

## Reflection loop

Run plan -> execute -> verify, max 3 iterations.

Spawn subagents with the Agent tool: subagent_type
`acs:create-operations-planner` / `acs:create-operations-executor` /
`acs:create-operations-verifier` (fall back to the un-namespaced name if
the runtime rejects the namespaced one). Apply
`context.models.<role>.model` / `.effort` at spawn when not `"inherit"`; if
the runtime rejects the model or effort, FAIL the run with that error — no
silent fallback.

Communicate in XML per `schemas/acs-messages.xsd`. Example plan task:

```xml
<task skill="create-operations" phase="plan" ticket-id="SHOP-2" iteration="1">
  <objective>Read the PRD NFRs and the architecture set; decide bootstrap vs re-run; produce a file-by-file plan for the operations/ doc set, tailored to the detected stack.</objective>
  <inputs>
    <file>docs/product/prd.md</file>
    <file>docs/architecture/</file>
    <file>docs/operations/</file>
  </inputs>
  <constraints>
    <constraint name="output-files">release-process.md, runbooks.md, observability.md, incident-response.md, test-scheduling.md only — no other file</constraint>
    <constraint name="read-only">The plan phase mutates nothing.</constraint>
    <constraint name="required_sections:incident-response.md">Severity levels; Roles during an incident; Postmortem process</constraint>
    <constraint name="required_sections:observability.md">Logging, metrics, and alerting conventions; Dashboards; SLO/SLA notes</constraint>
    <constraint name="required_sections:release-process.md">Versioning and release-cut steps; Changelog discipline; Branch and tag conventions; Rollback procedure</constraint>
    <constraint name="required_sections:runbooks.md">Standard operating procedures; On-call escalation path; Incident triage steps</constraint>
    <constraint name="required_sections:test-scheduling.md">The /acs:test scheduling recipe; Example cron/CI snippets; Where results land</constraint>
    <constraint name="audience_style_profile">ops/SRE (runbook register)</constraint>
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
`<partition>/phases/create-operations/iter-<n>-<phase>.xml` at the phase
boundary, BEFORE starting the next phase.

Phases:

1. **Plan** — the planner reads the upstream doc-graph slice (PRD NFRs + architecture
   set), notes any gaps as `<questions>`, classifies bootstrap vs re-run, and produces
   the per-file outline. The planner also runs the shared ADR-0012 design-time
   doc-consistency step; any findings surface through the "Clarification ledger
   first" mechanism below (User interaction). Persist the plan.
2. **Execute** — executors write the doc set on the ticket branch (create
   the branch first — see Delivery). Decomposition is YOURS alone; subagents
   never spawn subagents. Typically a single executor — the five files are small and
   tightly coupled.
3. **Verify** — after ALL executors finish, spawn the verifier on the
   combined result. It judges fresh from artifacts only (never the
   executors' reasoning) and checks, all blocking:
   - all five planned files exist, no unplanned extra file;
   - the tailored content **conforms to the architecture set** (stack/technology
     claims match `architecture/hld/tech-stack.md` and the rest of the set);
   - required sections are present in each file;
   - the plan was followed exactly;
   - the changeset is docs-only;
   - **consistency**: any `consistency_findings` the planner surfaced (the
     shared ADR-0012 design-time doc-consistency step, see Plan above) were
     resolved or explicitly user-deferred in the clarification ledger.

   The verify task's `<constraints>` also carry each of the five files'
   `required_sections:<file>` and the `audience_style_profile` declared in
   the Plan task example above.

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
   slugified title — e.g. `task/SHOP-2-product-operations-doc-set` — and
   `git checkout -b` it from the default branch.
2. **Commit** (after the verifier passes): stage ONLY
   `<operations_path>/` and verify the diff is docs-only
   (`git diff --cached --name-only` — every path under
   `operations_path`). Commit with `settings.formats.commit_message`
   (default `{ticket_id} {summary}`), e.g.
   `SHOP-2 Add product operations doc set` (or `Regenerate …` on re-run).
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
`clarify.py add --skill create-operations --question "..." --answer "..." --ticket <ticket-id>`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`. If the user is unavailable or says "you decide": record the
decision with `--source assumption --rationale "..."` — assumptions surface
in the completion report's Findings and the PR body until a user confirms.
Before a needs_input handoff, record the outgoing questions as `open`
(`clarify.py add` without `--answer`).

Ask clarifying questions when genuinely ambiguous (AskUserQuestion or plain
questions) — at minimum: any gap between the PRD NFRs and the architecture set the
planner surfaces. Do not ask about things the PRD or the architecture set already
answers.

If you genuinely cannot reach the user (e.g. a non-interactive run), do not
guess — return a `<handoff skill="create-operations" ticket-id="<id>"
status="needs_input">` with the `<questions>` list instead.

## Context pressure

If your context is running low mid-run: flush in-flight work plus soft
context (mode decision, partial verifier findings, gotchas) to
`<partition>/phases/create-operations/handoff-context.md`, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --ticket <id> --summary "<done / in-flight / next / decisions>"
```

Tell the user the `continue_with` command it prints (re-running this skill
with the delivery-ticket id resumes via the Start section's resume form).

## Finish

MANDATORY final step — never skipped, also on failure:

1. Write `<partition>/phases/create-operations/result.json` per the
   result-document contract in INTERNALS.md. Canonical `states` keys (exact
   names): `operations` and `pr`. `files` entries are paths relative to `<path>/`:

```json
{
  "status": "completed",
  "stop_reason": "doc set verified against the architecture set; docs-only PR opened",
  "states": {
    "operations": {
      "path": "docs/operations",
      "files": ["release-process.md", "runbooks.md", "observability.md", "incident-response.md", "test-scheduling.md"]
    },
    "pr": {"number": 9, "url": "https://github.com/owner/repo/pull/9", "branch": "task/SHOP-2-product-operations-doc-set"}
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
   written `operations` files without `pr`). On handoff:
   `status: "handed_off"` plus `handoff_summary`.

2. Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-operations.py" --ticket <id> --result-file <partition>/phases/create-operations/result.json
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
## /acs:create-operations · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <stop_reason>
- **Results**: operations/ files written at `operations_path`; delivery ticket id; PR number/URL
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <partition files, repo paths, branch, PR URL>
- **Metrics**: iterations <n>/3 · <wall time> · ~<tokens in/out> · ~$<cost_usd>
- **Next**: `/acs:merge-pr <ticket-id>` after reviewing the docs PR
```
