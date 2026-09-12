# 0089 — Pipeline order is declared in `ship.yaml`; skills are independent; hooks keep input and safety brakes

**Status**: Accepted · **Date**: 2026-09-12

## Context

The delivery order lived in two places that had to be kept in agreement by
hand: `/acs:ship`'s prose ("Pipeline order" / "Picking the next step"), and
`acs_lib/gates.py`, where a single primitive — `_require_completed(tdir,
skill, ticket_id, hint)` — refused a skill until a named predecessor's last
run was recorded `completed`. Four gates called it: `create-design` required
`create-ticket`; `docs-sync` required `code` (and, separately, read the
`test` step directly); `create-pr` required both `code` and `docs-sync`.

That design bought one real property — you cannot silently skip a step — and
charged four costs for it:

- **A skill was not runnable on its own.** Re-running `/acs:docs-sync` on a
  ticket whose `code` run had been finalized `interrupted` was refused, even
  though docs-sync re-derives everything it needs from the branch diff. The
  remedy was always "re-run the predecessor", which is not always what the
  user wanted or what the situation required.
- **Order was unextendable.** Adding a step meant editing the gate table, the
  ship prose, and every test that pinned a refusal message — so the pipeline
  ossified at the shape it had.
- **A consumer could not change it.** The order was the plugin's, full stop.
- **The refusals were doing two different jobs under one name.** "You have no
  plan to implement" (an input the skill reads) and "`/acs:code` has not
  completed" (a position in a sequence) were both `GateError`s, so neither
  could be reasoned about separately.

Options weighed:

- **Keep the order gates, add a bypass flag.** Smallest change, but a bypass
  flag is an escape hatch on a mechanism whose whole value is that it has no
  escape hatch — and it would still leave the order duplicated in prose.
- **Move the order into a workflow engine with its own state.** A second
  state machine beside `pipeline-state.json`, which the plugin already has;
  rejected as duplicated truth.
- **Declare the order as data, evaluate it against the existing ledger, and
  narrow the hooks to what only they can check (chosen).**

## Decision

**The pipeline's ORDER is declared in `plugins/acs/workflows/ship.yaml`,** a
data file with `version`, `name`, `stop_after`, `max_parallel` and a list of
`steps` — each `id`, `skill`, `needs`, an optional `when`/`requires`
predicate, `args`, `boundary`, `on_fail`, `on_replan` and `exclusive`. A
consumer replaces it **wholesale** with `<repo>/.acs/workflows/ship.yaml`
(override, never a merge — a merged workflow is a third shape nobody wrote
and nobody can read). `plugins/acs/workflows/phases.yaml` is the companion
registry grouping every skill into exactly one of five phases (design, build,
test, ship, utility) and is the single source for the workflow schema's
allowed-skill enum, the README table and `/acs:metrics` grouping; a workflow
may name build/test/ship skills only, never `merge-pr` or `release`.

**The files are parsed by an in-plugin YAML subset, not a dependency.**
`acs_lib/yamlsubset.py` accepts comments, 2-space-nested mappings, block and
single-line inline lists, quoted/bare strings, integers, booleans and nulls,
and rejects anchors, aliases, tags, flow mappings, block scalars, tabs,
duplicate keys and inconsistent indentation — each with a line number. The
plugin's stdlib-only rule (ADR-0001, ADR-0006 of the packaging NFRs) is not
negotiable for a hook path, and the subset is small enough that a strict
parser is cheaper than the risk of a permissive one.

**`_require_completed` is deleted, and no gate reads another skill's run
status.** Each pre-hook now checks exactly two things:

- **Inputs** — what the skill itself reads: the partition resolves; `prd.md`
  for `create-architecture`; the architecture doc set for the bootstrap doc
  skills; `plan.md` for `code`; `plan.md` plus an `analysis.md` declaring
  `api_surface: true` for `create-api-contract`; a configured e2e suite plus
  at least one e2e-typed case in `test-cases.md` for `create-e2e-tests`.
- **Safety brakes** — refusals that protect correctness rather than sequence:
  the partition `.lock`; epics are never implemented; `create-pr` refuses a
  ticket whose recorded `code` run left `verifier_passed != true`;
  `merge-pr` requires a recorded PR reference.

Two brakes were deliberately **narrowed rather than kept as-is**.
`create-pr`'s verifier brake previously refused a ticket with **no** code run
at all, because an absent `code-state.json` reads as `verifier_passed is not
True`; it now refuses only a ticket that HAS a recorded code run whose
verifier did not pass, so a docs-only or hand-driven ticket can open a PR.
`create-design` keeps its `needs_design` input check and loses the
`create-ticket`-completed check, because the partition existing IS the thing
`create-ticket` produces.

**Out-of-order is an advisory, never a refusal.** When a hooked skill that IS
a step of the resolved workflow runs with unsatisfied `needs`, the pre-hook
prints exactly one stderr line — `acs: docs-sync normally follows code in
ship.yaml; code has not completed for MAR-12` — and exits 0. It is
suppressed by `settings.workflow.advisories: false`, for a skill that is not
a step, and whenever anything it reads cannot be read: an advisory that could
raise would have re-created the gate it replaced, so it is fail-silent by
construction and never appears on a refusal path.

**`/acs:ship` becomes a thin loop over `acs.py workflow next`, and takes a
ticket id.** `workflow next` evaluates the declared DAG against the ticket's
existing `pipeline-state.json` — no new state — and returns the READY steps.
A step is satisfied when its ledger status is `completed` or when it was
recorded `skipped` because its `when` predicate is false; a step recorded
`failed`/`interrupted`/`in_progress`/`handed_off` is simply ready again. The
`new_request` entry path is removed: `/acs:create-ticket` and
`/acs:create-design` are Design-phase work that runs before ship.

**Parallelism is a first-class outcome, not a side effect.** When more than
one step is ready, none is `exclusive`, and `max_parallel > 1`, the walk
reports `mode: parallel` and `/ship` runs each ready step as a **leg** — one
subagent, one git worktree, one leg branch cut from the ticket branch head —
merging the legs back in file order. In the default workflow this is what
makes `create-e2e-tests` and `docs-sync` run side by side. `code` is
`exclusive: true` and always runs alone.

**The predicate vocabulary is closed and named**: `design_approved`,
`api_surface_changed`, `e2e_configured`, `post_code_test_active`, plus
`post_code_test_fix_loops_cap` for `on_fail.max_loops`. A workflow naming an
unknown predicate fails validation with its line number, so a typo is caught
by `acs.py workflow validate` rather than at 2am mid-pipeline.

## Consequences

**Positive.** Every skill is now runnable on its own, which is what makes the
new Build/Test skills addable at all: five joined the pipeline by editing two
data files and adding their own hooks, with no change to any other skill's
gate. The order is inspectable (`acs.py workflow show`), checkable
(`validate`), and overridable per consumer. Parallel legs shorten the
post-code tail. And the two jobs the old refusals conflated are now separable
in both code and prose: an input refusal names an artifact and its producer;
a brake names a risk.

**Accepted cost: a skipped step is no longer impossible, only visible.** The
old gate made "run `/acs:create-pr` without `/acs:docs-sync`" unreachable;
today it is reachable, and what stands between a user and it is one advisory
line plus `/acs:ship` walking the declared order. That is a real reduction in
enforcement, taken deliberately: the enforcement it removes was also what
made a legitimate re-run impossible, and the failure it now permits is
visible in `pipeline-state.json` rather than silent.

**Behaviour change for scripts, not only for prose.** Anything that detected
"not ready yet" from a pre-hook's exit code 2 will now see exit 0. The
replacement signal is `acs.py workflow next`, which answers the question the
exit code was being read as a proxy for.

**The advisory is best-effort and says so.** It reads the same ledger the
walk reads, but it never raises: a corrupt workflow file, an unreadable
ticket or a missing partition makes the line disappear, not the skill fail.
A user who needs a guaranteed answer runs `workflow next`.

**Known limitation, accepted.** `ship.yaml` is resolved and validated at use
time, not at install time, so a consumer override with a semantic error (a
cycle, a `needs` pointing forward, an unknown predicate) is discovered on the
first `/acs:ship` after it is written. `acs.py workflow validate` exists
precisely to be run before that, and `/acs:setup` points at it, but nothing
forces it.
