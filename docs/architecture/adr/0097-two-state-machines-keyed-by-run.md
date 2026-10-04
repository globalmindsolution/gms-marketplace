# 0097 — Two state machines, keyed by the run: `run.json` and `steps/<skill>/state.json`

**Status**: Accepted · **Date**: 2026-09-20

**Amends**: [0086](0086-in-repo-anchored-state-machine.md) (where the
workspace lives is unchanged; what it is keyed by is not)

**Related**: [0096](0096-workflow-is-a-list-not-a-graph.md)

## Context

The ledger was one machine doing two jobs. `pipeline-state.json` held the
ticket's position in the pipeline and a `steps` map; each skill also kept
`<skill>-state.json` with a `runs[]` array. Four things were wrong with that
shape, and each had produced a live defect.

**The partition was keyed by ticket, but not everything acs runs is about a
ticket.** A run from a prompt or from a document had nowhere to live, so
those skills either minted a synthetic ticket or wrote outside the ledger.

**A skill the workflow does not name could not keep state without taking a
position in the pipeline.** `/acs:create-design` is not a step of
`ship.yaml`. Recording its run wrote a `steps.create-design` entry, which the
walk then had to be taught to ignore. The two facts — "this skill ran" and
"the pipeline is here" — were stored in one place, so they could not be
separated.

**The cursor was stored, so it could disagree with the ledger.** The
pipeline's position was a field that a writer set, beside the step statuses
it was supposed to summarise. Any writer that updated one without the other
produced a ledger that contradicted itself, and the reader had no way to know
which half to believe.

**`handed_off` and `skipped` were not states.** `handed_off` is a *reason* a
step stopped — the work is interrupted, and the reason is that the session
ended. Storing it as a status meant "interrupted" and "why" shared one field
and could not both be expressed. `skipped` was a decision the workflow made
about a skill's applicability (ADR-0096), asserted by a predicate that never
read the change. A third confusion sat in `<skill>-state.json`'s `runs[]`:
each entry was one *invocation* of that skill, but a RUN is the whole pass
over the workflow, so the same word named two different things one directory
apart.

## Decision

**Two machines, separate on purpose.**

- **The run** — `runs/<run-id>/run.json` — the workflow it is running, the
  subject it is about, the loop iteration, the run's own status.
- **The step** — `runs/<run-id>/steps/<skill>/state.json` — that step's own
  `invocations[]`, its states, its artifacts.

Keeping them apart is what lets a skill the workflow never names keep step
state and take **no** position in any run.

**The cursor is DERIVED, never stored:** the first step in workflow order
that is not `completed`. `acs.py run next` computes it on every call, so it
cannot disagree with the ledger it is read from. A corrupt or missing state
file reads as *not completed*, which re-offers the step rather than letting a
half-recorded one count as done.

**A step is `in_progress | completed | failed | interrupted`.** `handed_off`
and `skipped` are retired. A `stop_reason` belongs to an `interrupted` step
only and comes from a closed set of three — `session_end`, `needs_input`,
`context_pressure`. A completed or failed step's narrative goes in `summary`,
where it is prose rather than a value something might branch on.

**Step state records `invocations[]`,** because a RUN is the whole pass over
the workflow and a step is invoked within it.

**The run id is derived from the subject, and nobody has to remember one.**
Ticket `MAR-590` runs as `MAR-590`; a prompt as its slug plus four hex
characters (`fix-the-login-timeout-3f2a`); a document likewise. A second run
on the same subject is `…-r2`. The four hex characters exist only so two
prompts that slug the same do not collide. A checkout's current run and step
live in `sessions/<checkout-id>/pointer.json`, so resuming needs no id at
all.

**Five invariants are checkable on demand** with `acs.py run check`, among
them **I1** (at most one `in_progress` step per run) and **I5** (a `steps`
entry the workflow does not name is refused — the rule that makes the
separation above enforceable rather than merely intended).

**The step root is the present; `iter-<n>/` is the past.** `plan.md` at
`steps/create-impl-plan/` is *the* plan; `iter-1/plan.md` and `iter-2/plan.md`
are the plans there were. The `iter-<n>-*` filename-prefix scheme and the
`phases/` artifact level are both gone, and there is exactly ONE plan, which
`plan_sha256` hashes.

ADR-0086 is unchanged in what it decided: the workspace is still anchored at
`<main_repo_root>/.acs/state-machine`, still gitignored, still shared across
worktrees, `workspace_path` still the override.

## Consequences

**A run is resumable from `run.json` alone**, and finding the run never needs
its id, because the checkout points at it.

**`/acs:handoff` writes a truth it could not write before:** the in-flight
step is `interrupted` with `stop_reason: context_pressure`. Previously the
same situation was `handed_off`, which said why and lost what.

**Non-ticket subjects are first-class.** A run from a prompt or a document
has a real partition, a real ledger and a real resume path.

**Migration:** run-keyed replaces ticket-keyed with no adapter — a v0.4.9
partition does not resume. `migrate_workspace.py`'s preflight reads both the
old flat `<skill>-state.json` and the new `steps/<skill>/state.json` layouts
so it can report accurately on either. Ticket **documents** are a separate
matter and do migrate: `acs.py artifacts migrate` moves them into
`docs/tickets/<ID>/`.

**What this gives up:** two files to read instead of one when debugging a
run, and an id per run rather than per ticket. The second is the point — two
runs over one ticket were previously indistinguishable in the ledger.
