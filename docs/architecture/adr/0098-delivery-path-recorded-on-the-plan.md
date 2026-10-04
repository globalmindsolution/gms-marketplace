# 0098 — The delivery path is judged by the plan and recorded in it, not configured on the workflow

**Status**: Accepted · **Date**: 2026-09-20

**Amends**: [0095](0095-static-delivery-path-routing.md) — the path stays
judged ONCE from the plan; what changes is **who** judges it and **where** it
is written.

**Related**: [0096](0096-workflow-is-a-list-not-a-graph.md)

## Context

ADR-0095 retired the `size` × `stakes` lane grid and made the delivery path a
single judgement from `plan.md`. That was right, and nothing here reverses
it. But it landed the judgement in two places it does not belong.

**`/acs:ship` judged it.** The coordinator read `plan.md` after
`create-impl-plan` completed, applied a rubric, and wrote the verdict. So a
ticket driven by `/acs:ship` had a path and the same ticket driven by hand
did not — and `/acs:code`, invoked standalone, either found no path or had to
judge one itself, which is a second judge (exactly the plurality ADR-0095
existed to remove).

**`ship.yaml` configured it.** A `delivery:` block declared `classify_after`
and the path vocabulary, and steps carried `paths: [...]` to opt out of
paths. That is a condition in the workflow about the change, which ADR-0096
removes for the reasons given there — and it put the vocabulary of the
judgement in a file the consumer overrides, so a consumer's workflow could
silently disagree with the legs the plugin ships.

**The verdict lived on `pipeline-state.json`,** which is run-ledger state,
while the evidence it was derived from lived in the plan. Two artifacts, one
fact, and the one that got reviewed in the PR was the plan.

## Decision

**`/acs:create-impl-plan` judges the delivery path, once, from the plan's own
scope, and writes it into the plan.** The plan is the first artifact that
names the files, the tests and the surfaces, so it is the first place the
judgement can rest on evidence. The plan ends in one section of fixed shape:

```
## Contract
delivery_path: standard
owes:
  api_contract: true
  test_cases:   true
  e2e:          false
  reason: "CLI-only change; no HTTP surface, no browser flow"

### Executor tasks & file map
- task 1: src/acs/hooks/scripts/acs_lib/run.py, tests/acs/test_run.py
```

Everything above `## Contract` is free-form prose, written for a human to
approve in one read. `plan_sha256` hashes the **whole** file, prose and
contract alike, so editing either invalidates the approval.
`### Executor tasks & file map` keeps its exact heading because the file-map
guard and `plan-approval.py` already key on it.

**Three readers, three reasons.** `delivery_path` — `/acs:code` dispatches to
`code-<path>`. `owes` — the always-run steps read it and record an evidenced
no-op when nothing is owed (ADR-0096). The file map — the executor partition
and the contract the write guard enforces.

**`acs.py path show | set` and `ship.yaml`'s `delivery:` block are removed**,
along with the per-step `paths:` key. There is one writer and one record.

**`acs.py plan path` is how a skill reads it.** `/acs:code` reached the
contract through heredoc Python inside its SKILL.md, which is the pattern ADR
0001 exists to prevent; the command replaces it and writes nothing.

**A plan that understates the work is caught at review, and its remedy is a
replan.** `/acs:review-code` raises it as a blocking finding; the step ends
`failed` with a summary naming the plan as superseded, and the run
re-enters `/acs:create-impl-plan`, which rewrites the Contract. There is no
mid-run raise, so one run never carries two rigors.

## Consequences

**A hand-run `/acs:code` gets the same path a shipped one does**, because the
path came from the plan both of them read.

**The judgement is reviewed where it is made.** `plan.md` is committed under
`docs/tickets/<ID>/` and appears in the PR, so the recorded reason is
reviewable prose rather than a ledger field nobody opens.

**A consumer cannot silently re-vocabulary the paths.** The four paths and
their legs ship inside the plugin; the consumer's workflow file has nothing
to say about them.

**Standalone `/acs:code` with no plan at all** derives an implicit plan from
its own read-only survey and judges the path from the same rubric — but only
onto the two cheap paths. A survey that judges the work `standard` or
`complex` stops with `needs_input` and asks for a real plan, because a plan
you wrote for yourself and then approved by implementing is not an approval.

**What this gives up:** the path can no longer be forced from the outside for
an experiment — there is no `--path` and no settings key. Re-judging means
editing the plan, which invalidates its approval and shows up in the diff.
That is the intended cost.
