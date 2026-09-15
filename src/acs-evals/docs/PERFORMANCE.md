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
right skill, and does a description of an internal leg's subject reach its
entry point rather than the leg), and whether pipeline runs reach a completed
status at all. A pipeline run counts as completed only when the session exited
clean **and the measured skill's own ledger** (`<ticket>/<skill>-state.json`,
`runs[-1].status`) says `completed` — a clean exit alone is not enough. On
2026-09-14 two `PIPE-code` sessions exited 0 after routing the old free-text
prompt to `/acs:ship`, which ran `/acs:analyze-ticket` and stopped: `/acs:code`
never ran, its ledger did not exist, and "not failed" scored both as
completions of a skill that was never exercised. Scenario set 1.7.0 therefore
also names the skill in the prompt (`/acs:code TKT-1`) and brings the sandbox
to the state its gate requires (`/acs:analyze-ticket`, `/acs:create-impl-plan`
as `setup_prompts`) — the scenario measures the skill's body, and the routing
decision is `ROUTE-code`'s to measure. Every pipeline session's stream-json
transcript is kept under `<out dir>/transcripts/` (`--transcripts` moves or
disables it), so a run that came back wrong is read, not re-bought.

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

The explicit probes (the six internal legs, plus `/acs:install-hooks`,
`/acs:update` and `/acs:test`) are cheaper still. A typed slash command is
expanded by the CLI itself and never dispatched through the `Skill` tool, so
such a probe can only be observed as **registered**: the `init` event's
`slash_commands` list. Those probes are decided at `init`, before any model
turn. They pin that the command still resolves — a user invokes a leg
directly to resume an interrupted delivery ticket. Every routing run records
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
- **Routing, negative probe** — passes only if the skill routes on **no** run.
  The six probes are the six **internal legs**: a plain description of a leg's
  own subject must reach its entry point (`/acs:create-docs`,
  `/acs:project`), which coordinates the fan-out, rather than the leg. It is
  `major`. It was `critical` while it guarded `disable-model-invocation`, a
  CLI-enforced guarantee; what it guards now is a description steering
  preference, and a user who lands on a leg still gets a working leg — just
  one doc set instead of the coordinated pass. Recording the drop here rather
  than quietly restating the floor.
  **A request is not an invocation.** No skill sets
  `disable-model-invocation` today, but the rule the flag needs is kept
  because the flag is CLI-enforced: a flagged skill is still listed in the
  session's `skills` and the model does reach for it, the CLI refuses the call
  outright (`cannot be used with Skill tool due to disable-model-invocation`),
  and the skill body never loads. A run is therefore decided by the Skill
  call's **tool_result**, not by the `tool_use` that asked for it: `detection`
  is `refused_user_only` and `routed_to` is `None`. That test is deliberately narrow — **only** a
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

## A measurement names its build, and the gate holds it to it

A measurement records the **content digest** of the plugin tree it
exercised (`build.digest`, from `harness.build_digest`): every byte under
`src/acs` that can change behaviour — skills, agents, hooks, schemas,
templates, workflows, the docs a skill reads at runtime — and nothing a
release cut rewrites (`plugin.json`'s version label, `CHANGELOG.md`). The
version string cannot do this job, because an unreleased tree shares one with
the release it supersedes; the skill-surface fingerprint tier 1 uses cannot
either, because it reads a rewritten SKILL.md or a deleted agent as the same
build, and those are exactly what tier 3 is run to judge.

Two rules follow, and together they are what makes the gate a gate:

- **`make perf` judges a measurement of THIS build or refuses.** A
  measurement whose digest is not the build under test's — or that records
  none — is `UNMEASURED (stale)`, a failing state, and `results/perf.json`
  says so. The plugin changed since the numbers were taken, so the numbers
  are about something else.
- **`make measure` is a no-op for a build already measured.** When
  `results/measurements.json` is a complete measurement of the identical
  build against the identical scenario set, covering the requested scope,
  nothing is spent: re-running it would buy noise, and a gate that re-spent
  hours on every re-run would get skipped. Any change to the tree, the
  scenario set, or the scope spends; `--force` (or
  `make measure MEASURE_ARGS=--force`) measures the same build again on
  purpose, which is what calibration does.

`/acs:release` runs this repo's gate — `make eval-source`, `make measure`,
`make perf` — before it edits anything, and stops on the first non-zero exit.
Fix what the gate reported, re-run the cut, and only the changed build is
measured again.

## The verdicts

| State | Condition |
|---|---|
| **UNMEASURED** | No measurement exists. Exit non-zero. |
| **BLOCKED (critical)** | A control probe failed, or a `disable-model-invocation` skill actually ran (no skill sets the flag today; the rule stands in case one does). |
| **BLOCKED** | An absolute floor was crossed. |
| **UNCOMPARED (baseline established)** | Floors held; first measurement for this scenario set, so nothing to compare. |
| **PASSED (uncalibrated drift)** | A provisional relative threshold was crossed. Look, do not block. |
| **PASSED** | Floors held and no axis regressed past its threshold. |

**UNMEASURED is the default, and it fails.** Absence is not a pass. The failure
mode this whole tier exists to fix is a green report that quietly means less
than a reader thinks, so it may never be green by having run nothing.

## Cost of the tier itself

`make measure-plan` prints it before anything is spent. At the shipped scenario
set that is **220 sessions**: 35 routing probes (32 routing, 3 controls) × 5
runs (each a few seconds, killed at the first `Skill` call, or at `init` for
the explicit probes and controls) plus 5 pipeline scenarios × 3 runs, each
run preceded by its scenario's setup prompts (two of the runs are full
`/acs:code` TDD cycles, and two more run one as setup). `make measure-routing`
runs the cheap half alone. Scenario set 1.4.0 added the two scenarios on the
fixture app (`PIPE-code-app`, `PIPE-docs-sync-app`) and gave `PIPE-docs-sync`
the `/acs:code` setup prompt its gate requires — a scenario whose measured
skill needs prior pipeline state names that state's prompts in
`setup_prompts`, run first in the same sandbox and recorded on the run's
`setup` list, never folded into the measured cost or time. 1.7.0 spells those
prompts out as the explicit gated steps (`/acs:analyze-ticket`,
`/acs:create-impl-plan`, `/acs:code`) rather than a request that routes.

### A setup that falls short leaves a hole, not a failure

A setup prompt is another scenario's whole body, and it is a model session:
it can time out, and it can exit clean having stopped short of the state the
measured skill needs. Scenario set 1.6.0 gives each one its own
`setup_timeout_seconds` (sized by the scenario the prompt belongs to, not by
the cheap skill being measured) and a `setup_assert` — a shell command, run in
the sandbox with `ACS_PARTITION` and `ACS_TICKET_ID` bound, that states the
precondition in the dataset rather than assuming it.

Scenario set 1.8.0 adds a third precondition, `ticket_patch`: the fields the
`ticketed` profile's minted ticket lacks. That profile mints "Add user login"
with an empty description and no acceptance criteria (the title is pinned by
tier-1 goldens), so `/acs:analyze-ticket` correctly reported the ticket not
ready for planning, `/acs:create-impl-plan` asked its open questions and
stopped, and `PIPE-code` ran unmeasured — a dataset defect that read as a
plugin one. The patch is applied through `acs.py ticket save --from -`
(PATCH semantics, so it can never touch the axes or the lane) before the
setup prompts run; a patch that cannot be applied marks the run
`unmeasured`, for the same reason a failed `setup_assert` does.

One refusal is neither of those: the claude CLI declining a session because
the account's usage allowance is spent (`You've hit your session limit`).
Nothing about the plugin was exercised, so the run is not `unmeasured` and
not a failure — the measurement **stops at the first one**, writes nothing,
keeps its checkpoint, and exits 4 saying so. Repeating the command after the
limit resets resumes from the checkpoint. Before this, each refused run cost
a sandbox and was recorded as `unmeasured`; two PIPE-code runs were
"measured" that way in twelve seconds on 2026-09-14.

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

### The prompt is the whole prompt, and the workspace is editable

Two harness defects the 2026-09-14 release-gate measurement exposed, both
fixed in the runner rather than the dataset:

- **stdin.** `claude -p` appends a non-tty stdin to its prompt, and a child
  process inherits its parent's stdin. The gate ran `make measure` from a
  shell loop reading its command list from a file, so 25 of the 27 pipeline
  sessions were prompted with the scenario text plus the three gate commands
  and spent their first turns looking for a `src/acs-evals` the sandbox does
  not have. Every `claude` the runner spawns now gets `stdin=DEVNULL` —
  pipeline sessions, routing probes and the registration read alike — so the
  prompt a scenario states is the prompt the session sees, whatever the
  caller's stdin.
- **`--add-dir`.** Under `acceptEdits` a headless session may edit only its
  working directory and the directories it was given. The acs workspace sits
  beside the sandbox repo (`workspace_path: ../ws`), so a coordinator's
  Edit/Write into its own partition was refused; one PIPE-docs-sync run was
  interrupted exactly there. Pipeline sessions now receive the sandbox
  workspace as an additional directory.

- **The minted ticket's ledger.** A scenario whose skill mints the ticket
  (PIPE-create-ticket on the `seeded` profile) starts with no ticket id, and
  the ledger read looked for `create-ticket-state.json` at the partition
  root — never where the skill wrote it. Every such run scored "never ran",
  including runs whose transcripts end with the post-hook's `completed`. The
  reader now finds the one ticket directory the run created.

- **The build is staged outside any checkout.** Resolved in place, this
  marketplace's build is `src/acs` inside the checkout running the
  measurement, and every command a skill embeds names that path. Two of
  three PIPE-create-ticket sessions took it for the project, `cd`'d into the
  checkout before `skill-start.py --allocate`, and minted two tickets in the
  marketplace's own workspace from inside a sandbox — locked, in progress,
  invisible to the measurement. The runner now copies the build to a temp
  directory (same content digest, so the same identity) and passes that as
  `--plugin-dir`; the same stray `cd` finds no `.acs/settings.json` above
  it, and `skill-start.py` refuses where it used to write elsewhere.

- **Setup budgets are per prompt, and sized to the slowest predecessor.**
  `/acs:analyze-ticket` took 780-840s on the two-line seeded ticket across
  the 2026-09-14 gate runs and over 900s once, which left a PIPE-code run
  unmeasured for nothing `/acs:code` did. Scenario set 1.10.0 gives each
  setup prompt of the code scenarios 1800s.

The routing half of the same gate found one split: `ROUTE-standardize-project-negative`
auto-invoked the internal leg on 1 of 5 runs (4/5 twice in three
measurements, 5/5 once). The leg's description led with "not a user-facing
entry point" and then described the audit-and-scaffold job in the words a
user would ask for it in; both `/acs:project` legs now open by refusing the
request outright and naming `/acs:project` as the only route. A negative
probe passes only when it never auto-invokes, so 4/5 is a finding, not
noise, whatever the odds of a single miss.

The app profile then exposed the cost of a verifier that treats citation
precision as truth: the app-profile `/acs:analyze-ticket` passed on its third
iteration at 1799s and was killed at 1800s, and iterations 2 and 3 had been
spent entirely on citations naming the right file at the wrong lines. Every
verifier charter now blocks on a source that says otherwise, a missing file
or an uncited fact — and notes, rather than blocks on, a wrong line number
with the fact intact. Scenario set 1.11.0 also gives the app scenarios 2700s
per setup prompt: a realistic ticket still takes analyze-ticket 15-25
minutes.

What the same gate found in the plugin, and what changed: a SMALL-lane
`/acs:create-impl-plan` setup on 2026-09-15 failed at its two-round ceiling
because the coordinator's draft stated, uncited and wrongly, that the
coverage package was not installed — in two sections — and its one revision
fixed one of them; the skill's fast lane now carries the executor's grounding
rule and a fix-every-occurrence rule for the revision. Of the two
measured SMALL-lane `/acs:code` runs one failed at the light lane's
iteration cap on a single coverage finding — the executor had topped up
coverage by appending manual CLI invocations, the verifier re-measured from
the suite and found 44%, and a cap of 1 gave the executor no round to fix
it. ADR-0034 was amended: light is 2 execute→verify rounds (the pass plus
the one iteration on findings it always described), and the executor's
charter says how coverage is measured.

- **A routing miss keeps its stream.** Routing probes are killed at the
  first Skill call and kept nothing, so a miss was undiagnosable:
  `ROUTE-create-prd` split 4/5 on 2026-09-15 after 20 straight hits, with
  `routed_to: null` and no Skill call in the stream, and nothing could say
  what the model did with its four seconds. The stream every probe's
  decision reads is now teed to a file, and a miss (by the gate's own hit
  rule) is kept beside the pipeline transcripts as
  `<stamp>-route-<probe>-run<n>.jsonl`.

- **A measured session does not inherit the launcher's session.** The
  runner is launched from inside a Claude Code session (the release gate
  is), and `claude -p` reads the parent's environment: with
  `CLAUDE_AUTO_BACKGROUND_TASKS=true` every subagent spawn on the 2026-09-15
  gate was moved to the background and the coordinators waited on
  ten-minute sleep loops until a 1800s setup ran out; with
  `CLAUDE_EFFORT=xhigh` every session reasoned at the launcher's effort
  rather than the model's default. `child_env` now drops those and the
  session-binding variables (session id, messaging socket, compaction
  state) before any session is spawned.

**The create-prd routing split, and what was done about it.** On the
2026-09-15 gate `ROUTE-create-prd` came back 4/5 after 20 straight hits
across four measurements; the miss was a reply with no Skill call, and the
routing probes kept no stream at the time. A 20-run diagnostic under the
new instrumentation came back 20/20 — 44/45 overall, nothing kept to read.
That is not evidence of a description defect and not a pass either: the
probe's record was removed from the checkpoint and re-spent, alone, with
miss streams kept, and the measurement that was promoted carries whatever
that re-spend produced. A second split would have been read from its
stream and fixed; a routing probe is never re-spent twice.

Scenario set 1.9.0 also rewrote PIPE-create-ticket's prompt: it delegates the
ticket-record decisions, because `/acs:create-ticket`'s confirmation gate is
a design requirement that a headless prompt with nothing decided can only
ever hand off on (0/3 on 2026-09-14, the skill behaving as designed).

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
