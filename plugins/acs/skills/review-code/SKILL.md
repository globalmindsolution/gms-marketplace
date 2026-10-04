---
name: review-code
description: Review any branch, diff, PR or ticket's changes — with or without a ticket id, "this branch against main" or someone else's branch against origin/main — whenever the user asks to review, audit, examine, scrutinize, critique or check them; prefer it over a generic code review. Call it as your first action on such a request — do not Glob, Grep, Read, ToolSearch or look for a shell or git first: it runs git itself and finds the changeset and base ref. It reviews in three stages — five read-only lenses in parallel, one fresh-context adjudicator per candidate finding prompted to refute it, then a final gate running build, lint, the full unit suite and coverage. It never edits the code under review: its verdict is recorded in acs's own state outside the working tree, so "don't change anything", "no edits, just a verdict" and "just tell me what's wrong" requests are exactly what it is for. On blocking findings /acs:code reads the verdict and fixes them. Use after /acs:code, or on its own against any base ref.
argument-hint: "[ticket-id | prompt | document] [--base <ref>]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:review-code — the changeset review, and the
only place the full unit suite runs in the pipeline.

You do not write code. You do not fix findings. You judge a changeset and
write a verdict; `/acs:code` is what acts on it.

## What you are reviewing

The changeset is everything between the merge base of `--base <ref>`
(default: the repo's default branch) and HEAD, **plus the working tree** —
untracked files included. Inside a pipeline nothing is committed before
`/acs:create-pr` (ADR-0127), so the change under review is usually ALL
uncommitted: a review that read `git diff <base>...HEAD` would judge an empty
changeset and pass a tree that does not exist. Read it only through acs:

```bash
base_sha="$(git merge-base <ref> HEAD)"   # <ref> = --base, else the default branch
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" changes diff --since "$base_sha" --patch
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" changes diff --since "$base_sha" --name-only
```

Resolve it once, at Start, and freeze what you judged: run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" changes snapshot` and
record its `tree` as `reviewed_sha` — the working-tree snapshot every lens
judges, and the baseline `/acs:code` diffs its fixes from
(`acs.py changes diff --since <reviewed_sha>`). A commit sha would not do:
the reviewed change is not committed. Every lens task names `base_sha`, so every lens
reads the same changeset the same way.

## Start

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step review-code
```

This records the step `in_progress` and tells you the run, the iteration and
whether a previous verdict exists. `${CLAUDE_PLUGIN_ROOT}/docs/INTERNALS.md`
carries Start, resume-and-reconcile, context pressure and the completion
report — the parts every acs skill shares.

## Stage 1 — the lenses

Five lenses, spawned **in parallel**, read-only, running nothing. Each writes
`iter-<n>/lens-<A..E>.md` and returns its candidate findings. The five lenses
are ONE message whatever `settings.parallel.max_agents` says — five is the
review's own fan-out, not a wave of the cap. When lens B fans out (below),
its instances beyond the first run after that message, in waves of
`settings.parallel.max_agents` (default 4).

**The gate starts in the same turn.** In the message that spawns the lenses,
also start stage 3's commands as jobs (`${CLAUDE_PLUGIN_ROOT}/docs/INTERNALS.md`,
"Jobs: commands beside the agents"), so the suite runs while the lenses read:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" job start --name gate-build -- <the repo's build command>
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" job start --name gate-lint -- <the repo's lint command>
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" job start --name gate-suite -- <the full unit suite with coverage>
```

Build and lint are separate jobs so they run concurrently; the suite and its
coverage are one job, because one run answers both. This is safe because the
tree is frozen for the whole review: lenses and adjudicators are read-only and
you edit nothing, so the gate runs over exactly the changeset they judge. A
repo with no build step has no `gate-build` job; record that in `gate.json`.

| Lens | Judges | May read |
|---|---|---|
| A — Acceptance | requirement conformance, features delivered | `requirements.md`, the plan, `test-cases.md`, the diff |
| B — Changed-hunk defects | logic errors, security | **the diff and nothing else** |
| C — Contracts & architecture | API/data contract, design, plan conformance | `api-contract.md`, `design.md`, architecture docs, the plan |
| D — History & regression | revert/hotfix patterns on the touched lines | `git log --follow -p`, bounded lookback |
| E — Craft & scope | quality, standards, simplicity, scope creep, documentation of the change | `standards/`, the diff |

**Lens B is defined by what it may not read.** It may not raise anything it
cannot establish from the diff alone. That constraint is what makes it a
different reviewer rather than a second copy of lens A. Give it the diff and
nothing else in its `<context>`.

**Lens E judges the change's own documentation, and blocks on it.** A change
that adds a flag, an endpoint or a config key and leaves the README, the
API/usage docs or the changelog saying otherwise is a defect in the
changeset, not a follow-up: raise it as a blocking finding whose
`resolved_when` names the file. That is distinct from `/acs:docs-sync`'s
step, which re-derives the product doc GRAPH from the diff; this is the
repo's own prose about what just changed.

**Lens D runs on every run.** It is the cheapest lens and the highest-yield:
on MAR-583 it produced 4 of 9 blocking findings, two of them invisible in the
diff. Never drop it to save a spawn.

**Spawn in the foreground and wait on the result, never on a clock.** Spawn
each lens with the Agent tool as `acs:review-code-lens` (fall back to the
un-namespaced name only if the runtime rejects the namespaced one), passing
`run_in_background: false`: the lens reports are your next input and nothing
else can usefully happen while they run. "In parallel" means one message
carrying every lens spawn, not a background launch you poll. If the runtime
moves an agent to the background anyway, wait for its completion notification
— never poll with `sleep` loops (`for i in $(seq 1 40); do sleep 15; done` and
its kin), which wait a fixed interval whatever the agent did. The same rule
governs stage 2's adjudicators.

### The reviewer scales itself

**Up.** A changeset too large for one reviewer's context is why `code-complex`
used to spawn four verifier lenses. That concern moved here with the review.
Lens B therefore fans out across the diff when the diff warrants it — one
instance per coherent slice, each still bound by "the diff and nothing else".
Measure the changeset yourself; never take a fan-out count from `/acs:code`
or from `ship.yaml`.

**Down, by the same rule: a lens runs when its inputs exist.** Lens C judges
conformance to the API contract and the design; on a run whose
`create-api-contract` recorded `no_surface_owed` and whose subject has no
`design.md`, it has nothing to judge — record that in `lens-C.md` and do not
spawn it. Lens A without `requirements.md` falls back to the subject
(§3.11); with neither, it records that it had no requirement to judge against.

What **never** scales down, on any delivery path: lenses A, B, D and E,
per-finding adjudication, and the gate. There is no rigor setting, and you do
not read the delivery path.

## Stage 2 — adjudication

**Every candidate finding gets exactly one fresh-context adjudicator.** Spawn
them in parallel, one `acs:review-code-adjudicator` per finding, at most
`settings.parallel.max_agents` (default 4) per message; more findings than
that run in waves of that size, each wave one message, the next only after the
last returned.

Each adjudicator receives: the finding, the requirement's intent, and read
access to the cited evidence. It receives **neither the other findings nor
which lens raised it** — a finding must survive on its own evidence.

It is prompted to **refute**, and defaults to refuted when uncertain.

| Verdict | Effect |
|---|---|
| `confirmed` | blocks; carries a `resolved_when` |
| `refuted` | dropped, with its reason recorded in `iter-<n>/adjudication.json` |
| `needs-context` | downgraded to advisory and carried — never silently dropped |

**A confirmed finding leaves adjudication with a `resolved_when`**: the
refutation criterion the adjudicator could not satisfy, restated as what a fix
must make true. That field is what `/acs:code` works to, so it is not
optional and it is not a restatement of the claim.

**Corroboration is not a filter.** On MAR-583 iteration 1 all three blocking
findings were single-lens; counting agreement would have shipped a broken
changeset. Per-finding re-derivation is the filter. Never drop a finding for
being raised by only one lens, and never promote one for being raised by two.

## Stage 3 — the final gate

Its result counts **only** when stage 2 leaves nothing blocking. Run all four
yourself — the jobs you started beside the lenses — and record the commands
and their output in `iter-<n>/gate.json`:

- **build** succeeds
- **lint** clean
- **full unit test suite** green
- **coverage ≥ `settings.tests.coverage`**

After adjudication:

- **Nothing blocks** → collect the gate with ONE blocking call, and call it
  again while it exits 3 (timeout, still running) — never `sleep`:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" job wait --name gate-build --name gate-lint --name gate-suite
  ```

  Each job's command, exit code and log are its evidence; read the coverage
  figure from the suite job's log. Record `gate.json` from them exactly as a
  gate you ran in the foreground.
- **Findings block** → stop the jobs (`acs.py job stop --name <each>`) and
  record the gate as not run for this iteration: the changeset is going back
  to `/acs:code` and the tree is about to change.

This is the only place the full suite runs in the whole pipeline. It runs
once per iteration, beside the review, and its result is read last, only by
an iteration that survives review. A gate failure is a blocking finding of
`kind: gate` with the failing command as its evidence — it needs no separate
channel and does not skip the loop.

## The verdict

Write `verdict.json` at the step root (and a copy in `iter-<n>/`). Findings
carry the fields `/acs:code` needs to act without re-deriving your work:

| Field | Why |
|---|---|
| `id` — `F-<iter>-<n>` | stable across iterations, so the next review can close it |
| `status` | `confirmed` or `advisory`; refuted findings are **not** here |
| `severity`, `kind`, `lens`, `file`, `line` | what and where |
| `claim` | one sentence |
| `evidence` | so `/acs:code` does not re-derive what you established |
| `resolved_when` | what the fix must make true |
| `traces_to` | `TC-n` / `AC-n` when a lens can name them |

`passed` is **not yours to assert**: the post-hook derives it from this
document (MAR-523/527). Write the findings honestly and let the kernel
conclude.

## On iteration 2+

Every lens receives the previous verdict's confirmed findings and
`/acs:code`'s `result.json` resolutions as context, and reviews the **whole
changeset** — a fix can break something the first review passed. Prioritise
hunks changed since `since_sha` (`acs.py changes diff --since <since_sha>`
— the snapshot the previous review judged), but do not restrict to them.

- a finding whose `resolved_when` now holds → `status: resolved` in the new
  verdict, so the trail shows closure
- a finding that still holds → **keeps its id** and is confirmed again
- a new finding → a new id
- a finding `/acs:code` marked `disputed` → its adjudicator receives the
  dispute as additional evidence and rules again. **Disputed and then
  confirmed a second time stops the run** with `stop_reason: needs_input`: a
  human breaks the tie rather than the last iteration being spent on the same
  argument.

The gate runs again in full, started again beside that iteration's lenses.

## Finish

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-review-code.py" --result-file "<the result.json you just wrote>"
```

`outcome` is read from your `result.json` and must be one of `passed`,
`blocking_findings` or `exhausted`. On `blocking_findings` the kernel
increments the loop and points the cursor back at `code`; you do not decide
that and you do not invoke `/acs:code` yourself.

A completed review without a usable `verdict.json` is refused: the review's
conclusion is a document the kernel reads, not a status you assert.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list` and reuse any
recorded answer — re-asking an answered question is a defect. When ≥2
clarifications are open, present them in ONE grouped interaction rather than
serial round-trips, and record each answer as its own entry with
`clarify.py add --skill review-code` — one `C-<n>` per question. Never skip a
question, never merge two into one entry, and never auto-answer one outside
the `--source assumption --rationale "..."` rule. When the user is
unavailable, record the decision as an assumption under that rule.

You rarely need this: a review judges what is in front of it. The one case
that does is a finding disputed and then confirmed a second time — a human
breaks the tie, and the question goes in the ledger before the run stops with
`stop_reason: needs_input`.

## Completion report (normative)

Every terminal outcome of a direct invocation ends your final message with the
standard block (`${CLAUDE_PLUGIN_ROOT}/docs/INTERNALS.md`, "Completion
report"), rendered only AFTER `step finish` succeeded. Same labels, same
order, `none` where empty:

```markdown

## /acs:review-code · <run-id> · <status>

- **Subject**: <id or title> (<kind>)
- **Status**: <status> — <outcome>
- **Results**: lenses run; candidate findings raised; confirmed / refuted / advisory after adjudication; the gate's four checks and coverage vs target
- **Findings**: <confirmed findings by id, or "none">
- **Artifacts**: `verdict.json`, the lens reports, `adjudication.json`, `gate.json`
- **Metrics**: iteration <n>/<cap> · <wall time>
- **Next**: `/acs:code` on blocking findings; `/acs:docs-sync` then `/acs:create-pr` on a pass (the reviewed change stays uncommitted until `/acs:create-pr`)
```
