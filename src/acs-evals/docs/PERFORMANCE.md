# Tier 3 — skill quality, reliability, cost and time

The deterministic tier asks whether the plumbing still emits the same bytes.
This tier asks the four questions a release actually turns on:

> Did the skills get **less reliable**, **worse**, **more expensive**, or
> **slower**?

Nothing in tiers 1 and 2 answers any of them. `METHODOLOGY.md` used to list all
four as out of scope; this tier is what changed that, and that file now points
here.

## Why the deterministic tier cannot answer them

Every tier-1 expectation is a recorded byte string. A release that made every
skill twice as slow, three times as expensive, and worse at routing would match
all 502 of them and print **PASSED**. That is not a defect in tier 1 — pinning
contracts is what it is for — but it means a green tier-1 run is evidence about
*contracts*, never about *skills*.

## The two halves

| | `runner/measure_skills.py` | `runner/perf_gate.py` |
|---|---|---|
| What it does | Runs the controlled scenario set against a build | Judges a measurement against a baseline |
| Needs | `claude`, network, money | Nothing — stdlib, offline |
| Output | `results/measurements.json` | a verdict, and `results/perf.json` |

Split for the same reason tier 1 splits recording from comparing: a measurement
bought once can be re-judged under new thresholds without paying again.

## What is measured, and from where

**Reliability** — routing accuracy per skill (does a natural request reach the
right skill, and do `disable-model-invocation` skills stay silent), and whether
pipeline runs reach a completed status at all.

**Cost** — `cost_usd` per run. For pipeline scenarios this comes from acs's own
ledger, `<ticket>/<skill>-state.json`, which is the same document `/acs:usage`
bills from — so the evaluation and the product cannot disagree about what a run
cost. `role_usage` is carried through, so a cost rise can be attributed to the
planner, executor, verifier or coordinator rather than just observed.

**Time** — wall clock, measured by the collector rather than read from the
ledger, because the ledger's own timing is part of what is under test.

**Quality** — verify iterations to pass, achieved coverage against the repo's
configured target, and whether a run finished carrying an unresolved blocking
finding. Iterations-to-pass is the closest thing the pipeline records to a
quality measure: it counts how often the executor's first answer was not good
enough, and it costs money on every ticket.

Routing probes record **no cost**. The session runs with `--tools Skill`, so
routing is the only move available to it, and is killed at that call's result
— that is what keeps a probe to time-to-route instead of a whole
skill body, and it is why the flag matters: under `--allowedTools Skill` alone
the model kept all 38 built-in tools and a probe could turn into a working
session. Killed that early it never emits a cost envelope. `cost_usd` is `null` rather than
estimated; an invented number in a cost baseline is worse than an absent one.

The two explicit probes (`/acs:install-hooks`, `/acs:update`) are cheaper
still. A typed slash command is expanded by the CLI itself and never dispatched
through the `Skill` tool, so `disable-model-invocation` skills can only be
observed as **registered**: the `init` event's `slash_commands` list. Those
probes are decided at `init`, before any model turn. Every routing run records
`detection` — `skill_tool_use`, `registered`, `refused_user_only` when the CLI
declined to dispatch the call at all, `skill_tool_use_unresolved` when the
stream ended before the call's result arrived, or `unmeasured` when an explicit
probe's stream reported no registration list at all, which the gate counts as
a miss, never a pass.

## The decision rules

Stated here because `METHODOLOGY.md` is right that `runs: 3` with no declared
rule is not a criterion.

- **Routing, positive probe** — passes only if it routes to the expected skill
  on **every** run. A split result is a finding, never a pass. Routing is
  stochastic; one green run is not evidence. A probe runs in the sandbox its
  prompt presupposes — `profile` and deterministic `setup` steps in
  `routing.json` (default: the `ticketed` seed) — because a prompt about
  "this existing codebase" on an empty repo tests the model's patience, not
  the description; a split is triaged against the sandbox before the
  description (scenario set 1.5.0).
- **Routing, negative probe** — passes only if the skill auto-invokes on **no**
  run. This is the `disable-model-invocation` guarantee, and it is `critical`.
  **A request is not an invocation.** A flagged skill is still listed in the
  session's `skills`, and the model does sometimes reach for it — but the CLI
  refuses the call outright (`cannot be used with Skill tool due to
  disable-model-invocation`) and the skill body never loads, so the guarantee
  held. A run is therefore decided by the Skill call's **tool_result**, not by
  the `tool_use` that asked for it: `detection` is `refused_user_only` and
  `routed_to` is `None`. That test is deliberately narrow — **only** a
  `disable-model-invocation` refusal undoes a route. Every other error on a
  Skill call happens *after* dispatch, and the commonest by far is the skill's
  own pre-hook declining to work in the probe's sandbox (`acs pre-code:
  blocked — no plan.md found for TKT-1`). That is a correctly routed probe:
  the right skill was chosen and invoked, and its gate refused the work, which
  is all a probe killed at the routing decision ever wanted. Counting those as
  misses would invert the positive half of the suite. The attempt is kept in the run's `attempted` and
  reported as a `minor` **routing-quality** finding — the descriptions are
  pointing the model at a skill only a user may run, which costs a turn and is
  worth fixing in prose. Scoring the request as the invocation is what made the
  2026-09-13 measurement report two CRITICAL findings against a guarantee that
  had in fact held on all fifteen runs.
- **Controls** — three probes whose answer is known before the run: a
  registration canary (`/acs:setup`) that must hit, an unregistered command
  (`/acs:no-such-skill`) that must miss, and an off-domain request (a poem)
  that must route nowhere. They test the instrument, not the plugin, and a
  failed control is `critical` because nothing measured around it can be
  read. The two explicit controls also run as a free **pre-flight** before
  any paid session: if the sandbox cannot see the plugin, `make measure`
  stops there, spends nothing and writes no measurement.
- **Cost, time, iterations, coverage** — compared as the **median** across
  runs, never a single run, so one timeout cannot move the number a release is
  judged on. The min/max spread is recorded alongside, because that spread is
  what calibration reads.

## Absolute gates block; relative gates are opinions until calibrated

This is the part that keeps the tier honest.

**Absolute** gates — routing accuracy, run completion, unresolved blocking
findings — are definitions, not measurements. A positive probe that routes on
four runs of five is unreliable whatever any baseline says. These block on the
very first measurement, with no baseline needed.

**Relative** gates — cost, time, verify iterations, coverage — are ratios
against a recorded baseline. A ratio nobody has calibrated against observed
noise is an opinion, and an opinion that blocks releases trains people to
override the gate. So while `dataset/thresholds.json` carries
`basis: provisional`, relative findings are **reported and never block**. The
verdict for that state is `PASSED (uncalibrated drift)` — a prompt to look, not
a claim of a defect.

A measurement records its `scope` — `full`, `routing` or `pipeline` — and is
`incomplete` only when it did not finish that scope. A routing-scoped run that
finished is promotable as `dataset/baselines/acs-<version>-routing.json`; the
gate compares routing probes against it, names the partial scope in its
verdict, and a full baseline supersedes it.

`calibration_protocol` in that file is how they stop being provisional: run
`make measure` repeatedly against one unchanged build, and the spread that
produces is the tier's noise floor. Set each ratio outside it with margin,
record the measurement in `calibrated_from`, and set `basis` to `calibrated`.
A threshold tighter than the noise floor makes the gate a random number
generator; one far looser makes it decorative.

## The verdicts

| State | Condition |
|---|---|
| **UNMEASURED** | No measurement exists. Exit non-zero. |
| **BLOCKED (critical)** | A `disable-model-invocation` skill actually ran (its Skill call was honoured), or a control probe failed. |
| **BLOCKED** | An absolute floor was crossed. |
| **UNCOMPARED (baseline established)** | Floors held; first measurement for this scenario set, so nothing to compare. |
| **PASSED (uncalibrated drift)** | A provisional relative threshold was crossed. Look, do not block. |
| **PASSED** | Floors held and no axis regressed past its threshold. |

**UNMEASURED is the default, and it fails.** Absence is not a pass. The failure
mode this whole tier exists to fix is a green report that quietly means less
than a reader thinks, so it may never be green by having run nothing.

## Cost of the tier itself

`make measure-plan` prints it before anything is spent. At the shipped scenario
set that is **159 sessions**: 30 routing probes (27 routing, 3 controls) × 5
runs (each a few seconds, killed at the first `Skill` call, or at `init` for
the explicit probes and controls) plus 3 pipeline scenarios × 3 runs (one of
which is a full `/acs:code` TDD cycle). `make measure-routing` runs the cheap
half alone. Scenario set 1.4.0 adds two scenarios on the fixture app
(`PIPE-code-app`, `PIPE-docs-sync-app`; 165 sessions in all) and gives
`PIPE-docs-sync` the `/acs:code` setup prompt its gate requires — a
scenario whose measured skill needs prior pipeline state names that state's
prompts in `setup_prompts`, run first in the same sandbox and recorded on the
run's `setup` list, never folded into the measured cost or time.

### A setup that falls short leaves a hole, not a failure

A setup prompt is another scenario's whole body, and it is a model session:
it can time out, and it can exit clean having stopped short of the state the
measured skill needs. Scenario set 1.6.0 gives each one its own
`setup_timeout_seconds` (sized by the scenario the prompt belongs to, not by
the cheap skill being measured) and a `setup_assert` — a shell command, run in
the sandbox with `ACS_PARTITION` and `ACS_TICKET_ID` bound, that states the
precondition in the dataset rather than assuming it.

When either gives way the run is marked `unmeasured`, and the difference
matters more than it looks:

| | What it means | Whose bug |
|---|---|---|
| `unmeasured` | the setup never reached the state the scenario declares, so the skill was never run | the harness or the dataset |
| a run that completed with `status: failed` | the skill ran and did not finish | the plugin |

An `unmeasured` run leaves the reliability denominator and every median the
gate compares, and is reported on its own **coverage** axis — major severity,
absolute, so it blocks. Scoring it as a reliability miss files a harness defect
against the plugin; dropping it silently lets a release quote a floor nothing
was measured against. Both happened in the 2026-09-13 measurement, which is
why this exists: `PIPE-docs-sync` reported 2/3 and `PIPE-docs-sync-app` 0/3
for a skill that had, on the app profile, never once been reached.

## The fixture app

The pipeline scenarios on the `app` profiles run on `dataset/fixtures/app`
(`runner/fixture_app.py`): a real order-management service with tests, a
coverage floor of 85 that can bite, docs the ticket makes stale, 32 commits of
history including a revert, and `orders/payments/**` under `high_stakes_paths`
so the stakes trigger has something to fire on. Its content is hashed into
`scenarios.json` (`fixture_hash`), and measurements carry `set_hashes` for the
routing and pipeline halves separately, so a routing baseline is not thrown
away when the fixture or a pipeline scenario changes.

### Seeded defects — the verifier's catch rate

`dataset/fixtures/app/defects/` holds seven changesets that leave the
fixture's own test suite **green** and are wrong in exactly one way a named
code-verifier dimension must catch: a business-logic off-by-one behind an
adjusted test, tax rounding broken behind a test that asserts nothing, a
committed live key, a dead duplicate function, a doc contradicted by the diff
(expected `info` — consumer-doc drift is advisory by design), an unrelated
rewrite inside a scoped ticket, and an untested module that drops coverage
under the floor. A defect the tests catch would never reach the verifier, so
it would measure nothing about it; `make defects-selftest` proves each one
still applies and stays green. Feeding them through the verifier is the paid
measurement: `make catch-rate` (plan it with `make catch-rate-plan`) seeds
each defect on the ticket branch of an `app-ticketed` sandbox and runs one
`/acs:code` session per defect, so the verifier judges a branch diff that
carries the defect; a defect is caught when the owning dimension produces a
finding at the expected severity in the verifier's own verdict document. Its
output is a per-dimension catch rate — the number `make verifier-rates` cannot
give you — and one run per defect is a screen, `CATCH_RUNS=3` the statistic.

The pipeline set is deliberately three scenarios, not twenty-five.
`scenarios.json` names every skill it excludes and why, so the gap is
reviewable rather than merely absent.

## Status and limitations

**No measurement of acs has been taken yet.** `dataset/baselines/` is empty and
the thresholds are provisional. What is verified today is the comparator: 22
cases in `runner/test_perf_gate.py` assert the decision rules hold against
synthetic records. Those records test the arithmetic and the rules and say
**nothing whatever** about acs.

Known limitations, worst first:

1. **The scenario set is a sample of three pipeline runs.** Cost and quality
   findings generalise to the surfaces those three touch and no further.
2. **Sandbox runs are not consumer runs.** The scenarios use a throwaway repo
   with a trivial change. Real tickets are larger, and a cost baseline taken
   here understates real spend — it is useful for *deltas between releases*,
   not as an estimate of what a consumer pays.
3. **Model changes confound build changes.** A cost or quality delta can come
   from the model behind `claude`, not from acs. `environment` records the CLI
   version for exactly this reason, and a delta across a model change should be
   re-baselined rather than triaged as a regression.
4. **Three runs is a small n.** Enough to satisfy the routing rule (which needs
   unanimity, not a mean), thin for medians on cost and time. Raise
   `runs_per_scenario` when the budget allows; the spread in each record says
   whether it needs raising.
