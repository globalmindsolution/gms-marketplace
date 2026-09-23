# The `## Contract` block — field reference

The block's SHAPE is in `create-impl-plan/SKILL.md` under `## Contract`, because every plan writes it. This file carries the per-field reasoning and
the edge cases, which you only need when a field's value is not obvious.

`--skill code` and `--iteration 1` are deliberate: the map this plan declares
is the map `/acs:code`'s first iteration of executors is checked against, and
an undeclared map means no enforcement at all. `/acs:code` re-declares it for
its own remediation iterations. Record the returned `tasks` object as
`states.file_map`.

### Verify (per iteration) — this IS the plan review

Spawn `acs:create-impl-plan-verifier` AFTER the draft is written, with
`<inputs>` of the draft, the ticket file, `analysis.md` and `design.md` when
they exist, every `<partition>/specs/*.md`, and the repo paths the file map
names. The verifier judges fresh — never forward the executor's reasoning —
and writes `steps/create-impl-plan/iter-<n>/verify.md`. Its
`<result>`'s `<findings>` is the verdict: `status="completed"` means
verification RAN, and an empty `<findings>` is the pass. Never conclude a pass
the verifier did not report.

ALL blocking findings block — zero blocking findings = pass. On findings:
persist the verify output, then AUTOMATICALLY re-execute, passing every
finding to the next iteration's executor in `<context>` with no plan phase
in between. After the ceiling of **3** execute → verify rounds with findings
remaining: stop with final status `"failed"`, the findings recorded, and
NOTHING published: on a first run `/acs:code`'s gate then stays shut because
the artifact it requires was never written, and on a re-plan the ticket keeps
the plan it already had rather than gaining an unverified one.

### Publish — the coordinator is the only writer of `plan.md`

Once the verifier passes, publish the draft. **The coordinator performs this
step itself, never a subagent:** the file-map write guard
(`acs_lib/filemap.py`) denies any running executor a write under the ticket
docs tree, because the plan is precisely the control input an executor is
checked against. Copy, never re-author — the published bytes must equal the
verified bytes:

```bash
draft="steps/create-impl-plan/plan.md"
mkdir -p "$(dirname "<plan_path>")" && cp "$draft" "<plan_path>"
```

Then commit `<plan_path>` on the ticket branch when it is inside the repo
(the docs tree active); the run's own copy is workspace state and is never
committed.

### Plan approval happens later, not here

Approval binds on the `standard` and `complex` delivery paths only — and this
skill runs before any path exists, because `plan.md` is the artifact the path
is judged FROM. So `plan-approval.py` is not run here.

A human approves the plan with `plan-approval.py`, which is the **sole writer**
of `plan-approval.json` — never a coordinator, never an executor, and never a
Write-tool call, because a record a skill can write itself is not an approval.
It hashes `steps/create-impl-plan/plan.md` into `plan_sha256`, and `/acs:code`'s
pre-hook refuses the deep paths when that digest does not match the plan on
disk. An edited plan is an unapproved plan.

What this skill owes approval is therefore one thing: **publish the plan and
leave it alone.**

### Docs-only tickets (`ticket.docs_only: true`)

When the ticket carries the user-confirmed `docs_only` flag the plan changes
shape, not rigor: plan NO new tests and no coverage measurement — plan the
single full-suite run that proves the change breaks nothing, and state
`coverage_target: "n/a — docs_only"` in the test strategy. The file map lists
doc paths only. If the ticket cannot be delivered without touching executable
code or tests, the flag is wrong: surface that to the user (User interaction)
rather than planning around it.
