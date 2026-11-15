# What the plan says — the planner's survey and the plan's shape

Read this when you task the planner and when you judge whether its draft is
ready to send to review: what the authoring notes cover, the shape `plan.md`
takes, the `## Contract` block downstream code reads, and what every plan
carries however short.

## What the authoring notes cover

The planner's authoring notes cover, in the order
`create-impl-plan-planner.md`'s survey defines:

- Analysis of the subject: implementation order, ambiguities and explicit
  clarifying questions (surface these — see User interaction — before the plan
  is published).
- The decomposition: typically ONE executor task per coherent slice, each
  listing the exact repo files it will touch (source, tests, docs) — this file
  map decides whether `/acs:code` may run its implementers in parallel, and it is
  what the PreToolUse write guard enforces.
- The test strategy per slice: which failing tests to write first, the repo's
  test/coverage tooling and the exact commands to run them, how
  `settings.tests.coverage` will be measured.
- The documentation map: whether any factual claims in `docs/product/prd.md`
  or `docs/product/roadmap.md` are made stale by the change (factual items:
  agent/subagent counts, shipped-vs-planned status, topology, version numbers,
  file path references) — `/acs:docs-sync` independently re-derives every
  other doc-delta (README/API/usage/changelog, the architecture doc set, ADRs)
  from the diff after `/acs:code` completes.
  The planner also performs a bounded, touched-area ADR-0012 doc-graph-gap
  check (`create-impl-plan-planner.md`'s survey item 4, edges E1-E4) — not the
  full shared design-time step `create-tech-design`'s designer runs — riding the same
  `problems` carrier as the existing Boy-scout drift item.
- Risks, and what a reviewer should look hardest at.

## The plan's shape

**The plan is written for a human to approve in one read.** It works the way
Claude Code's own plan mode works, which is a deliberate borrowing of a shape
already proven and already familiar:

1. **Read-only until approved.** The survey investigates with read and search
   tools only. The planner writes exactly one file — the plan draft — and
   nothing else; no production code, no tests, no repo docs.
2. **Concrete steps against real paths**, the approach and the alternative
   rejected, and what is explicitly NOT being done. Prose and bullets, as
   short as the change allows.
3. **Approval is an explicit act and it is the gate** (see "Plan approval
   happens later, not here"). Feedback re-enters planning rather than leaking
   into implementation.
4. **Approval binds to the text that was approved** — `plan-approval.json`
   records `plan_sha256` over the approved bytes, so an edited plan is an
   unapproved plan.

**It is not a template.** There is no section-per-heading checklist to fill in
whether or not that heading has content: a `## Risks` heading with "none"
under it is worse than no heading, because it grades the document on its shape
rather than on what it says. Write what this change needs and stop.

**The machine-readable minimum.** "Not a template" is not "no structure":
three things downstream code reads must be findable without parsing prose, so
the plan ENDS with one section of fixed shape and everything above it is
free-form.

```markdown
## Contract
delivery_path: standard
owes:
  test_cases:   true
  e2e:          false
  reason: "CLI-only change; no HTTP surface, no browser flow"

### Executor tasks & file map
- task 1: plugins/acs/hooks/scripts/acs_lib/run.py, tests/acs/test_run_machine.py
- task 2: plugins/acs/skills/ship/SKILL.md
```

Three readers, three reasons:

- **`delivery_path`** — `trivial | small | standard | complex`, judged ONCE,
  here, from the plan's own scope (`skills/code/references/classify.md` is the
  rubric). `/acs:code` dispatches to its leg from it; nobody picks a path by
  hand and nothing re-judges it. Prefer the more expensive path whenever two
  fit: an unnecessary lens pass costs tokens, a missed regression in a
  load-bearing path costs more.
- **`owes`** — whether `/acs:create-test-docs` and the e2e steps have work
  on this run (an `api_contract` key a plan written before ADR-0134 carries is
  ignored: the API contract is a Design document now, not a step this plan
  settles). Each of those steps reads its own flag
  and records an evidenced no-op when the answer is false; **silence is not
  permission to skip**, so a step whose flag is absent does its work and
  decides for itself. `reason` is one sentence a reviewer can check.
- **the file map** — the executor partition, and the contract the file-map
  guard enforces on every Write. When the run has an API contract and the repo
  keeps machine-readable contract files, the task that creates or updates
  them from the contract names them here. `### Executor tasks & file map` keeps its
  exact heading because the guard and `plan-approval.py` already key on it.

`plan_sha256` hashes the whole file, prose and contract alike, so editing
either invalidates the approval. A skill that needs a value reads the
`## Contract` block and nothing else; a human reads everything above it and
need not read the block at all.

**The plan IS the spec content.** There is no separate spec set and no
separate spec-authoring step: what a standalone create-spec planner would once
have written — the scope, the approach at contract level, the API and data
changes, the test plan, what is out of scope — is simply part of what the plan
says, in whatever shape this change needs. Two things that content must carry
wherever it lands: every `requirements.acceptance_criteria` entry maps to at least
one test the plan will write, and `settings.tests.coverage` is stated
explicitly. The approval predicate checks the second mechanically; the
plan reviewer checks the first.

**Oversize signal pointer.** `create-impl-plan-planner.md`'s survey item 2
compares this decomposition against the reviewable-diff bar; when it fires,
the split seams recorded above are what `/acs:breakdown-ticket` reads (see
User interaction for the split-answer termination).

**Short is not empty.** A plan that says "see ticket", or a file map with no
files in it, fails the plan reviewer's completeness sub-check and the approval
predicate alike. What every plan carries, however short: the AC-to-test
mapping, the executor file map, the test and coverage commands, the
`docs/product/prd.md`/`docs/product/roadmap.md` factual assessment, and the
`## Contract` block. The remaining survey items — the Boy-scout drift survey,
the E1-E4 doc-graph-gap check, the simplicity gate and the oversize signal —
are best-effort; their omission is never a finding.

## Why planning has one shape

**One shape, on every run — and it could not be otherwise.** This skill runs
BEFORE the delivery path exists: `plan.md` is the artifact the path is judged
FROM, and its own `## Contract` block is where the judgement is recorded
(ADR-0095; the workflow's old `delivery:` block is gone). A plan skill that
branched on the path would be reading a decision its own output has not yet
been made to produce. So there is no fork here, and the ceiling is a fixed
**3** planner → plan-review rounds. Iteration 1's planner surveys before it
writes.

That symmetry is worth stating plainly: every ticket gets the same planning
rigor, and the plan is what earns a cheap or expensive implementation. Spending
less on a plan because someone guessed the work was small is exactly the
guess ADR-0095 removed.

## Docs-only tickets (`ticket.docs_only: true`, ticket runs only)

When the ticket carries the user-confirmed `docs_only` flag the plan changes
shape, not rigor: plan NO new tests and no coverage measurement — plan the
single full-suite run that proves the change breaks nothing, and state
`coverage_target: "n/a — docs_only"` in the test strategy. The file map lists
doc paths only. If the ticket cannot be delivered without touching executable
code or tests, the flag is wrong: surface that to the user (User interaction)
rather than planning around it.

## A bug — the first test reproduces it

On a `bug` ticket (ADR-0138) the plan's first slice opens with a **failing
reproduction test**: the FIRST test of the FIRST executor task, written before
any fix, named for the behaviour that is broken (`test_reset_link_expires_before_email_arrives`
— never the ticket id), built from the reproduction the analysis recorded (its
`## Scope and summary`) and the ticket's `reproduction`, `expected` and
`actual`. `## Test strategy` says it fails before the fix and passes after
it, which is the ticket's regression criterion. When the analysis could not
reproduce the bug, the plan says so and plans the test from the ticket's steps,
flagged as unconfirmed. The plan reviewer checks this (its dimension 5).
Nothing else about the plan's shape changes.
