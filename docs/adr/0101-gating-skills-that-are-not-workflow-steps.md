# 0101 — Gating a skill that is not a workflow step: a third pre-step table, and a run projected for the query

**Status**: Accepted · **Date**: 2026-09-21

**Amends**: [0089](0089-pipeline-order-declared-in-ship-yaml.md) (the two
brakes it kept per-skill stand and are restored; "nothing in the gate layer
reads a predecessor's run status any more" is narrowed, because `/merge-pr`'s
brake reads whether the step that recorded the PR completed),
[0096](0096-workflow-is-a-list-not-a-graph.md) (the list still decides ORDER
and membership; it never decided whether a skill is GATED, and the gate no
longer reads it as if it did)

## Context

v0.5.0 replaced the seventeen per-skill gate functions and the `GATE_INPUTS`
family split with one generic input gate that reads `skills/<name>/acs.yaml`'s
`reads.required`, and kept per-skill only what is genuinely a safety brake:
`BRAKES`, holding `code` and `create-pr` (`acs_lib/brakes.py:153-156`). Two
brakes did not survive that move. `gate_create_design` and `gate_merge_pr`
existed at `06a0ab1^` and were deleted by `06a0ab1`;
`REDESIGN-IMPLEMENTATION-PIPELINE.md` §6 Removals lists **neither**, and its
scope line (`:5-9`) keeps the design skills — naming `create-design` — "out of
scope" and "their current shape". Nothing removed them on purpose.

They could not have survived in `BRAKES` either, and that is the decision this
ADR exists for. `gate_step` returns as soon as the resolved workflow does not
name the skill, and `BRAKES` is consulted after that return. `ship.yaml` v3
lists ten steps; `merge-pr` and `create-design` are not among them and must
not become steps. So for two releases both pre-hooks exited **0 with empty
stderr on every profile** — bare, ticketed and epic alike — while the control,
`pre-create-pr.py`, a skill that IS a step, kept exiting 2 correctly. A merge
with no PR reference anywhere was reachable; so was a design for a ticket that
was never flagged for one.

The same early return had a second victim. `acs gate` is documented as running
a skill's pre-gate without running the skill, and passes `mutate=False`
(`acs_commands.py:cmd_gate`) so that asking a question does not create a run,
take the lock, open a step or settle a no-op — the four side effects it used to
have, one of which permanently completed `create-e2e-tests` for anyone who
asked about it. With no current run, `resolve_run_for` answered
`(None, None, wf)`, and every check below it — the lock, the invariants, the
input fallbacks, `_brake_no_epics`, `BRAKES` — sat past that return. The query
reported `{"ok": true}` for an epic the hook refuses outright. Removing the
writes had cost the sight, and the two were not separable where the cut was
made.

So: **where does a gate live for a skill that is legitimately not a step of the
workflow?**

## Decision

**1 · A third table of the kind that already exists, consulted where they
are.** `gate_step` already gates non-step skills before it reads the workflow:
`ARCHITECTURE_GATED` (`create-project`, `standardize-project`, `create-docs`)
and `PRD_GATED` (`create-architecture`). `brakes.py:192-196` states the
principle verbatim — these preconditions are checked there "rather than through
a skill's `reads` declaration, because they are not run artifacts: a design or
product skill is never a step of `ship` (§2.4), so it has no run to read them
from."

`gates.SUBJECT_GATES` is that table for a precondition about the **subject
ticket** rather than a repo document: `{"create-design": gate_create_design,
"merge-pr": gate_merge_pr}`, each `f(ctx, payload)` raising `GateError` to
refuse. It is consulted immediately after `PRD_GATED` and **before** the
`has_step` return, unconditionally — because a safety brake must not be
switchable off by editing `ship.yaml`. A consumer who does add `merge-pr` to
their own workflow gets the brake *and* the run machinery, which is the right
answer in both directions.

The two functions live in `gates.py`, not `brakes.py`: that module's layer is
"resolves no context, takes no lock, writes nothing", and these resolve a
ticket.

**2 · This is a restoration, not a revert, and three pieces did not come
back.** The v0.4.9 bodies read `load_pipeline(tdir, ticket_id)` and
`state_path(tdir, skill)` and branched on `flow: ticket|product`. State is
run-keyed now and `flow` is a listed removal (§6), so the PR-reference lookup
is re-expressed: `_pr_recorded_for` walks `run.find_runs_for_subject(repo,
"ticket", id)` newest-first with `run.partition_for_ticket` as a fallback so an
archived run still answers, and for each of `("create-pr",) +
DELIVERY_TICKET_SKILLS` requires the step's state file to exist, its
`states.pr` to carry a `url` or a `number`, and `step.last_status` to be
`completed`. The lock check moves with the lock: it targets the **run**
partition, and is skipped when the ticket has no run yet.

**3 · `merge-pr` and `create-design` stay out of `ship.yaml`, and that is not
a compromise.** The run delivers a pull request and ends at `create-pr`;
merging is a separate decision about a PR that already exists, and
`/acs:merge-pr`'s exempt non-ticket forms (`--pr N`, `#N`, a PR URL) name no
ticket and no run at all — the gate short-circuits on them before it resolves
anything. `create-design` runs before there is a run to belong to, and its
precondition is a flag on the ticket (`needs_design`), which is exactly the
kind of condition ADR-0096 refuses to let a workflow express. Both facts point
the same way: the condition belongs to the skill, checked on its subject.
(ADR-0089 forbade a workflow from naming `merge-pr` at all, through
`phases.yaml`'s group rule; ADR-0096 dropped both. Nothing forbids it today —
these two simply are not steps, and the paragraph above is why that is right
rather than incidental.)

**4 · The query regains the hook's sight through a run projected in memory.**
`run.projected_run(repo, subject, wf, wf_path)` returns everything `create_run`
returns — the run id, the path the run **would** occupy, and the same document
— minus the directory creation, `save_run` and `index_run`. `create_run` is now
that function plus exactly those writes, so what the query judges and what a
real run records cannot drift apart. Under `mutate=False`, `resolve_run_for`
answers with the projection instead of "no run, nothing to check", and four
read-only consumers gained an optional `doc=` so they judge the document they
were handed rather than loading one that was never written: `run.check`,
`stepgate.check_invariants`, `stepgate.check_inputs`,
`advisory.workflow_advisory`. `gate_step`'s body moved to
`gates.gate_outcome`, which returns `GateOutcome(run_id, doc)` so the advisory
is rendered from the document the gate judged; `gate_step` stays as the
one-line wrapper its callers know.

Inertness is now **structural rather than cleaned up afterwards**: nothing is
written, so there is nothing to undo. `acquire_lock`, `_mark_step_started` and
`settle_no_op` stay `mutate`-guarded, and `cmd_gate` still passes
`record_marker=False`.

## Consequences

**The query is answerable for what it says.** `acs gate --skill <s>` now
produces the same exit code and the same stderr as `pre-<s>.py` for the same
subject — the input-fallback lines, the epic brake and the out-of-order
advisory included — while creating no run, taking no lock, opening no step and
settling no no-op. Anything scripted on its exit code will see refusals it did
not see before; they were always the hook's answer.

**Why this survived a release, recorded plainly, because it is the part that
generalises.** The regression was not unguarded. Three tests that existed to
guard exactly this ground stopped doing it, and stayed green:

- A unit test **asserted the absence of the behaviour as correct.**
  `tests/acs/test_planning_skills_registry.py::DispatchRoutingCase` required
  `pre-create-design` to exit 0, and its class docstring stated the premise —
  "the per-skill `gate_create_design` is gone… the pass-through is the
  behaviour under test". A test that pins a deletion ratifies it. It now
  asserts what is actually true: the skill takes no run position *and* is gated
  on its subject, which are different claims.
- A fail-closed test **bound to a name a refactor moved.**
  `tests/acs/test_dispatch_fail_closed.py` installed its fake gate on
  `gate_step`, the name the dispatcher used to look up. When the body moved to
  `gate_outcome` the fake reached nothing and the real gate ran — and three of
  the five cases still passed, because they asserted only `exit == 2` and the
  real gate also exits 2. The module's own docstring had warned about this
  exact trap for a different reason.
- Two ADR guards **pinned a count instead of the thing they guard**, which
  fails the other way — loudly, at the next legitimate amendment.
  `tests/acs/test_adr_0007_second_amendment.py:4` still promises "exactly
  three `## Amendment — ` headings"; its assertion (`:50-58`) and the matching
  one in `tests/acs/test_code_plan_doc_graph_gap.py:204-216` now pin the first
  N headings **and their order** instead, each with a comment recording that "a
  frozen count would forbid the next amendment instead of guarding these three
  against drift".

The pattern is one thing said three ways: **a test that asserts the ABSENCE of
a behaviour, binds to a NAME rather than a BEHAVIOUR, or counts instead of
checking, stops protecting anything the moment the code moves — and the first
two report success while doing so.** What caught all three was the golden
dataset, which drives the real binary and asserts the message a user sees:
GATE-011, 015, 026, 030, 042 and 045 went from FAIL to ok **byte-unchanged**,
with no case edited. An expectation recorded against behaviour outlives the
code that implements it; an expectation recorded against structure does not.

**ADR-0089's "no gate reads a predecessor's run status" needs one exception
named.** `/merge-pr`'s brake reads whether the step that recorded the PR
reference completed. That is not an order gate and does not reopen
`_require_completed`: it names an **artifact** (a recorded PR), not a position,
it refuses nothing for being early, and the exempt `--pr` form bypasses it
entirely. A PR reference written by a step that never finished is not evidence
that a PR exists, which is the whole content of the check.

**Accepted cost: a per-skill gate table exists again.** v0.5.0 removed
seventeen of them for good reasons, and this adds one back with two rows. The
boundary is therefore stated rather than left to judgement: a row belongs in
`SUBJECT_GATES` only when the skill is not a step of the workflow **and** its
precondition is a property of the subject ticket. Anything a run can answer
stays in the skill's `reads` declaration, where one declaration drives both the
gate and `acs workflow validate`.

**One recorded expectation is now unreachable, and it is recorded, not
quietly dropped.** `GATE-044` expects `acs gate --skill create-pr` on an epic
to exit 0. `create-pr` is in `_EPIC_VERBS`, and `GATE-042` — in the same
untouchable set — requires the query to *see* that brake. One mechanism cannot
point both ways: making 042 pass necessarily makes 044 exit 2. The four
advisory cases (028, 029, 043, 044) encode pre-v3 wording and the removed
`needs:` construct; they were left red and untouched, and carry to MAR-587.
