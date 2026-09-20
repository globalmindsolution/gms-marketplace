# /acs:code — the protocol every delivery path shares

*Read by whichever `code` leg is running. Path:*
*`${CLAUDE_PLUGIN_ROOT}/skills/code/references/protocol.md`.*

Four legs implement the `code` step — `code-trivial`, `code-small`,
`code-standard`, `code-complex` — and everything below is identical in all
four. What differs is how many executors run, how deeply the verifier looks,
and how many iterations the loop may take; that lives in each leg's own
SKILL.md, which is the only file that needs reading to know what a path costs.

**The legs share `code`'s identity on disk.** Every one of them starts with
`acs step start --skill code`, so the partition, `phases/code/`,
`code-state.json`, the `code` ledger key and `post-code.py` are the same
whichever leg ran. The leg name appears in exactly two places: the Skill
invocation, and the gate mapping that sends it through `code`'s own gate. A
resumed run therefore reads artifacts a different session wrote without
caring which leg wrote them.

---

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step code
```

If it exits non-zero: STOP and surface its stderr verbatim to the user. Do not
improvise a workaround. `pre-code.py` has verified this skill's inputs: the
ticket resolves to a live, unlocked partition, it is not an epic, and a plan
exists — the gate looks for `plan.md` in the ticket's docs folder and in the
partition, and refuses with "no plan.md found for `<id>` ... — run
/acs:create-impl-plan `<id>` first." when it finds none. The gate is
the same on every delivery path, requires no predecessor run to have completed
(the pipeline order lives in `workflows/ship.yaml`, not in this gate), and never
requires `specs/` to exist.

Parse the printed context JSON. Fields you will use:

- `ticket_id`, `ticket` — the resolved ticket (title, type, description,
  `acceptance_criteria`, `external`). The implementation must satisfy it.
- `partition` — absolute path of `<workspace>/<repo-id>/<ticket-id>/`. Read
  the ticket's `plan.md` (see Plan input resolution), `test-cases.md` and
  `api-contract.md` when they exist, and EVERY spec in `<partition>/specs/`
  (sorted `01-`, `02-`, ... — that is the dependency order). Phase artifacts
  go in `steps/code/`.
- `design` — `{required, dir, source}`. `design.dir` is the PARTITION of the
  ticket whose design applies (`source` is `"own"` or `"parent"` — child
  tickets use the parent epic's design); its basename is that ticket's id.
  When `design.required` is true, resolve the design document with
  `acs.py artifacts show --ticket <that id>` and read `artifacts["design.md"]`
  — the design ticket's docs folder, or `<design.dir>/design.md` when the tree
  is opted out. Call it `<design_doc>`; the changeset is judged against it.
- `settings` — you need `test_coverage_percent` (the hard coverage gate),
  `architecture_path`, `requirements_path`, `adr_path` (default `docs/adr`; `null` disables),
  `standards_path` (default `docs/standards`; `null` disables — when set,
  pass `<constraint name="standards_path">` to the **verifier only**, not to
  executors),
  `formats.branch_name`,
  `formats.commit_message`, and `e2e` (may be unset — when set, pass
  `<constraint name="e2e_command">`/`e2e_setup`/`e2e_teardown` to executors and
  the verifier. `e2e_per_iteration` is still accepted and still passed, but
  nothing reads it any more: it existed to let the verifier skip its full e2e
  run on some iterations, and the verifier no longer has one — the full e2e
  suite belongs to `/acs:run-e2e-tests`, which `workflows/ship.yaml` runs after
  `/acs:create-e2e-tests` has written the tests. What still gates the verdict
  here is the DIFF: a spec that declared e2e impact with no matching e2e test
  change is a blocking finding).
- `models` — per-role `{model, effort}` for executor/verifier (the planner
  entry is resolved for every skill; this one spawns no planner).
- `reconcile`, `handoff_summary`, `prior_run_status` — see Resume & reconcile.
- `post_hook` — absolute path to `post-code.py`.

---

## Subagents and messaging

Every leg spawns the same two agents — `acs:code-executor` and
`acs:code-verifier` — and obeys the same messaging rules. What a leg
decides is HOW MANY of each to spawn and how deep the verifier looks.

Spawn subagents with the Agent tool: `acs:code-executor` and `acs:code-verifier` (fall back to the
un-namespaced name only if the runtime rejects the namespaced one). For each
role, apply `context.models.<role>.model`
/ `.effort` at spawn when not `"inherit"`; if the runtime rejects the model or
effort, FAIL the run with that exact error — no silent fallback.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops (`for i in $(seq 1 40); do
sleep 15; done` and its kin), which wait a fixed ten minutes whatever the
agent did and spent a whole 1800s setup on the 2026-09-15 release gate.

Messaging rules (the SubagentStop hook's message check):

- Send each subagent one `<task skill="code" phase="execute|verify"
  ticket-id="<id>" iteration="n">` containing `<objective>`, `<inputs>` (file
  refs: the resolved `plan.md`, `test-cases.md` and `api-contract.md` when
  they exist, spec files, the ticket document, design.md when it applies, repo
  paths), and `<constraints>`. The subagent returns a `<result>` as its final
  content.
- Validate EVERY message you send and receive:

  ```bash
  ```

  On invalid: re-request once with the validation error; still invalid -> fail
  the run and record the error in the result document's `errors`.
- Persist every phase output to
  `steps/code/iter-<n>-<phase>.xml` at the phase boundary,
  BEFORE starting the next phase.
- Decomposition is YOURS alone — subagents never spawn subagents. You MAY run
  several executors in parallel ONLY when their specs touch disjoint files
  (per the plan's file map); any overlap — source, tests, or docs — means
  sequential execution. The verifier runs after all executors finish and
  judges the combined changeset.

---

### Epics are never implemented

An epic ticket is refused outright by the `code` gate before this skill ever
starts (`gate_code` raises `GateError` for `ticket.type == "epic"` — the
message the user sees comes from the gate). Every ticket that reaches this
step therefore has `ticket.type != "epic"`. If `ticket.type == "epic"`
nonetheless reaches this step (a bypassed or best-effort pre-gate on some
runtimes), STOP immediately and surface the same breakdown message
`gate_code` would have raised — never implement an epic under any
circumstance, regardless of what the pre-gate did or did not enforce.

This is defence in depth, and it is a rule of every delivery path: a leg that
somehow received an epic must refuse it exactly as the gate would, not judge
it onto a path and implement it.


---

## Branch — FIRST, before any code

All work happens on the ticket branch. Render `settings.formats.branch_name`
(default `"{type}/{ticket_id}-{slug}"`) with:

- `{ticket_id}` — `context.ticket_id` (e.g. `SHOP-123`);
- `{type}` — `ticket.type` (`epic|story|task`);
- `{slug}` — slugified ticket title: lowercase, every non-alphanumeric run
  becomes `-`, trimmed of leading/trailing `-`, max 40 chars (matches
  `acs_lib.slugify`);
- `{external_key}` — `ticket.external.key` when set, else empty string.

Then create or reuse it:

```bash
git rev-parse --verify --quiet "<branch>" && git checkout "<branch>" || git checkout -b "<branch>"
```

On resume the branch usually already exists — reuse it, never recreate or
reset it. Every commit message follows `settings.formats.commit_message`
(default `"{ticket_id} {summary}"`; same placeholders minus `slug`, plus
`{summary}`). Commit work on this branch as specs land; do NOT push —
/acs:create-pr pushes and opens the PR.

---

## Resume & reconcile

If `context.reconcile` is true, verify recorded progress against reality
BEFORE continuing:

1. Read `<partition>/code-state.json` (`runs[-1]` and `states`) and
   `steps/code/iter-*-*.xml` / phase artifacts to see which specs
   were recorded implemented and where the prior run stopped.
2. Check out the recorded `states.branch` (it should exist — see Branch).
3. Re-run the test suite — once. A single full run reports on every spec
   recorded implemented at the same time, and re-establishes coverage too when
   the test command reports it. Trust nothing that fails: a spec whose tests
   fail or whose files are missing is NOT done, whatever the state file says.
4. Continue from the first unfinished spec/phase of the recorded iteration
   (e.g. an execute report with no verify output -> rerun verify against that
   changeset; spec 02 green but 03 untouched -> resume at 03).

If `context.handoff_summary` exists, read it plus
`steps/code/handoff-context.md` (if present), do a light
reconcile (trust the summary, but cheaply verify by running the tests it says
pass), and continue from where it points.

### Plan input resolution

The plan is an INPUT here, never an output: `/acs:create-impl-plan` wrote it
and this skill reads it. Resolve it once, at Start:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" artifacts show --ticket <ticket-id>
```

`artifacts["plan.md"]` is the path the gate already resolved — the ticket's
docs folder (`<settings.artifacts.tickets_path>/<id>/plan.md`), the partition
(`<partition>/plan.md`), or the pre-docs-tree location
`steps/code/plan.md`, in that order. Pass THAT path to every
executor and verifier `<inputs>`; it is the one plan this run reads, in every
delivery path. Alongside it, `artifacts["test-cases.md"]` and
`artifacts["api-contract.md"]` are read when present (Execute and Verify
below).

**`steps/code/plan.md` is the approval mirror.**
`/acs:create-impl-plan` publishes a byte-identical copy there because
`plan-approval.py` — the sole writer of `plan-approval.json` — hashes that
path, and the verifier's plan-conformance dimension reads it. A mirror that
differs from the resolved plan is itself the "plan edited after approval"
signal the dimension exists to catch; never reconcile the two by editing
either.

**Never author or revise it.** If the plan is missing on resume, or execution
proves it wrong — a spec it does not cover, a file map that cannot work, an
approach the codebase refuses — do NOT re-plan here: stop at the iteration
boundary, write the result document with `status: "failed"` and
`stop_reason: plan_superseded` naming what the plan got wrong, run the Finish
steps, and point at `/acs:create-impl-plan <ticket-id>`. Under `/acs:ship`
that stop reason is what the workflow's `on_replan` edge reads.
`steps/code/plan-superseded-<k>.md` is written by
`/acs:create-impl-plan`'s revocation path, never here.

---

## Docs-only tickets (`ticket.docs_only: true`)

When the ticket carries the user-confirmed `docs_only` flag, the TDD steps
relax — the delivery and review guarantees do not: executors skip
write-failing-tests-first and new-test generation; the coverage hard fail
does not apply (record `coverage_percent: null`, target "n/a — docs_only");
the existing test suite is STILL run once and must be green (a docs-only
change that breaks the build is a finding); the verifier's Tests/Coverage
dimensions become "n/a — docs_only" while every other dimension still
applies in full — performed and reported per its own severity: Documentation consistency's
advisory sub-checks (per-commit doc-sync, living-requirements,
architectural-impact) stay advisory; its blocking Product-doc-consistency
sub-check stays blocking. If any executor finds itself touching executable
code or tests, STOP — the flag is wrong; surface it to the user and have the
ticket corrected before continuing.

---

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
`clarify.py add --skill code --question "..." --answer "..." --ticket <ticket-id>`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`. If the user is unavailable or says "you decide": record the
decision with `--source assumption --rationale "..."` — assumptions surface
in the completion report's Findings and the PR body until a user confirms.
Before a needs_input handoff, record the outgoing questions as `open`
(`clarify.py add` without `--answer`).

When a spec is genuinely ambiguous — contradicts another spec or the design,
undefined behavior, multiple plausible implementations with different
user-visible outcomes — ask the user before executing (AskUserQuestion or
plain questions). Do not guess on decisions that change behavior. Record the
answers; they belong in the execute reports and any handoff flush.

**The plan is not up for renegotiation here.** The oversize signal, the split
answer and any revision of the plan belong to `/acs:create-impl-plan` (its
User interaction section). If an ambiguity's honest resolution is that the
plan is wrong, end the run `failed` with
`stop_reason: plan_superseded` per Plan input resolution rather than
implementing around it.

If you genuinely cannot reach the user (e.g. a non-interactive run): do not
guess. Write the result document with status `"failed"` and
`stop_reason` "needs user input", run the Finish steps, and return as your
final message a handoff like:

```xml
<handoff skill="code" ticket-id="SHOP-123" status="needs_input">
  <summary>Specs 01-02 implemented and green; 03 blocked on an API question.</summary>
  <questions>
    <question>Spec 03: should DELETE /items/{id} soft-delete or hard-delete?</question>
  </questions>
  <next-step>Answer the questions, then re-run /acs:ship SHOP-123.</next-step>
</handoff>
```


---

## Context pressure

If your context window is running low mid-run: do NOT burn the remainder on
work that would be lost. Commit any uncommitted green work on the branch,
flush in-flight state plus soft context (user answers, decisions, partial
findings, which specs are green/in-progress, gotchas) to
`steps/code/handoff-context.md`, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --ticket <ticket-id> --summary "<done / in-flight / next / decisions>"
```

Tell the user the `continue_with` command it prints, and stop.

---

## Finish

MANDATORY final step — never skipped, also on failure:

1. Write `steps/code/result.json` per the result-document
   contract in INTERNALS.md:

   ```json
   {
     "status": "completed",
     "stop_reason": "verifier passed on iteration 2 with 0 findings",
     "states": {
       "verifier_passed": true,
       "branch": "task/SHOP-123-bulk-import",
       "specs_implemented": ["01-data-model.md", "02-import-endpoint.md"],
       "tests": {"passed": 84, "failed": 0, "coverage_percent": 93.4, "coverage_target": 90},
       "docs_updated": ["README.md", "docs/api/import.md", "docs/architecture/lld/flows/bulk-import.md"],
       "review": {"iterations": 2, "findings_open": 0}
     },
     "findings": [],
     "errors": []
   }
   ```

   **Five of these keys are DERIVED (MAR-523, MAR-578).** `verifier_passed`,
   `tests`, `pr`, `review.iterations` and `review.guard_denials` are
   **computed by the post-hook from the artifacts** — the verifier's verdict,
   the executors' execute reports, the forge, the guard's denial trail, and the
   verify files on disk. Write your best value anyway (the document is a
   contract with humans too), but what lands is the computed one,
   and a disagreement is written to `runs[-1].derived_states.overrode` and
   printed. You cannot open the /acs:create-pr gate by writing `true`.

   Canonical `states` keys — EXACT names; pre-create-pr.py gates on them:
   - `verifier_passed`: **derived** from the verifier's `verdict.json` for the
     highest iteration (MAR-527); no passing verdict means `false`, whatever
     the document says. This is the /acs:create-pr gate.
   - `branch`: the ticket branch name (rendered from `formats.branch_name`).
   - `specs_implemented`: spec basenames fully implemented AND verified, in
     order.
   - `tests`: `{passed, failed, coverage_percent, coverage_target}` — **derived**
     from the last iteration's `iter-<n>/verdict.json`, the verifier's own run
     of the suite, falling back to the `iter-<n>-execute*.json` reports when
     the verdict records no numbers (a docs-only ticket, or a run that ended
     before any verifier wrote one). `coverage_target` comes from
     `settings.test_coverage_percent`. Kept as you wrote it only when no
     execute report records a run.
   - `docs_updated`: repo-relative paths of every doc file changed.
   - `review`: `{iterations, findings_open}` — `iterations` is **derived** by
     counting the verify artifacts on disk; `findings_open` is yours (findings
     still open, 0 on success). `guard_denials` is **derived** too, from
     `runs[-1].guard_events` (the file-map guard's denial trail): never write
     it, and expect the key to be absent, not 0, when the guard never fired.

   Advisory documentation findings (`severity="info" dimension="documentation"`,
   from code-verifier's demoted per-commit doc-sync, living-requirements, and
   architectural-impact sub-checks) are carried into the `findings` array and
   named on the Completion report's `**Findings**` line, but are never
   counted in `review.findings_open` and never affect `verifier_passed` — a
   zero-blocking-findings run still reports `verifier_passed: true` and
   `findings_open: 0` with any advisory documentation entries present in
   `findings`.

   On failure keep whatever is true: `verifier_passed: false`, the branch,
   the specs that ARE implemented and green, the achieved
   `tests.coverage_percent`, docs actually updated, open findings in
   `findings` and `review.findings_open`, and the reason (coverage hard fail,
   iteration cap, needs input, `plan_superseded`) in `stop_reason`.
   `stop_reason: plan_superseded` is the one reason another skill reads: it
   says the plan — not the changeset — is what must change, and `/acs:ship`'s
   `on_replan` edge routes it back to `/acs:create-impl-plan` — not to a
   planning step here, of which there is none. Name what the plan got wrong in
   the same `stop_reason` so that skill starts informed.

2. Run the post-hook:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-code.py" --ticket <ticket-id> --result-file steps/code/result.json
   ```

   If it exits non-zero, surface its stderr verbatim — the pipeline gate
   stays closed until it succeeds.

3. Report a compact summary to the user: branch, specs implemented,
   tests/coverage vs target, docs updated, review iterations and open
   findings, and the next step (`/acs:docs-sync <ticket-id>` then
   `/acs:create-pr <ticket-id>` on success, or
   `/acs:create-impl-plan <ticket-id>` after a `plan_superseded` failure).
   Under /acs:ship, instead return ONLY the `<handoff>` XML as your final
   message — status, summary (<=1KB), `<artifacts>` listing the branch and key
   changed paths, and `<next-step>` pointing at the same next skill.

---

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty; under /acs:ship your final message is the `<handoff>` XML instead — this report is for direct invocations:

```markdown

## /acs:code · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <stop_reason>
- **Results**: branch; specs implemented; tests passed/failed; coverage achieved vs target; docs updated; review iterations and open findings
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <partition files, repo paths, branch, PR URL>
- **Metrics**: iterations <n>/<cap> · <wall time> · ~<tokens in/out> · ~$<cost_usd>
- **Next**: `/acs:docs-sync <ticket-id>` then `/acs:create-pr <ticket-id>` on success; on a coverage hard-fail or iteration cap, re-run `/acs:code <ticket-id>` after addressing the recorded findings; on `plan_superseded`, `/acs:create-impl-plan <ticket-id>`
```

Any advisory documentation flags (`severity="info" dimension="documentation"`,
from code-verifier's demoted per-commit doc-sync, living-requirements, and
architectural-impact sub-checks) surface on the **Findings** line above
alongside open blocking findings and clarifications, or `none` when there
are none.

The non-epic COMPLEX breakdown recommendation (Start / escalation steps
above), when surfaced during this run, also appears on the **Findings**
line — a signal only in internal step-prose is not "surfaced" (D7-C).
