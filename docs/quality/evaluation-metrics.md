# Evaluation metrics

**What a release is judged by, where each number comes from, and which PRD goal
it answers.** The rubric in [`skill-rubric.md`](skill-rubric.md) says how good a
skill is; [`behavioural-eval-rubric.md`](behavioural-eval-rubric.md) says what an
eval must assert to count as evidence; this doc says which numbers decide
whether a version ships, and which of the PRD's own goals those numbers cover.

The machine-readable source is
[`src/acs-evals/dataset/thresholds.json`](../../src/acs-evals/dataset/thresholds.json):
every threshold carries its `value`, `severity`, `rule` and `why`, and
`runner/perf_gate.py` reads that file rather than any number written here. Where
this doc and that file disagree, the file is right and this doc is stale.

## What the release gate runs, and why in that order

`/acs:release` runs `release.pre_release_gate` from `.acs/settings.json` and
stops at the first non-zero exit. Nothing else gates a cut.

| # | Command | Cost | What a failure means |
|---|---|---|---|
| 1 | `make -C src/acs-evals eval-source` | free, 20 s | A contract this build was recorded emitting has moved. |
| 2 | `make -C src/acs-evals check` | free, 1 s | A generated case tree or the fixture hash is stale against the plugin source. |
| 3 | `make -C src/acs-evals mutation` | free, 2 s | Schema-constraint coverage fell below its 0.9 floor. |
| 4 | `make -C src/acs-evals measure` | ~10 h, ~$150 | A skill stopped routing, stopped completing, or moved on cost, time or quality. |
| 5 | `make -C src/acs-evals perf` | free | The measurement, judged against the thresholds and the baseline. |

Steps 2 and 3 were added on 2026-09-16 and are the point of this ordering: both
are free, both fail closed on their own exit codes, and together they cost 3
seconds against a measurement of roughly ten hours. Before that, a release cut
ran only steps 1, 4 and 5, so a stale generated tree or a schema-coverage
regression could only be discovered after the measurement had been bought.

The Makefile's `gate` target is a different, looser thing: it runs `eval`
against the **installed** build rather than this checkout, so it answers a
question about whatever is in the plugin cache. It is a local sweep, not the
release gate, and its help text now says so.

## Observed run-to-run variance, and what it says about the thresholds

A threshold tighter than the noise floor makes the gate a random number
generator. Until now no measurement existed to place that floor. The
2026-09-15 run bought three runs of each pipeline scenario on one unchanged
build, which is a within-build spread — not a calibration, but the first real
evidence:

| Scenario | Metric | Min | Median | Max | Max / median |
|---|---|---:|---:|---:|---:|
| PIPE-create-ticket | cost, USD | 0.51 | 0.60 | 0.67 | 1.11 |
| PIPE-create-ticket | time, s | 81.2 | 93.3 | 97.4 | 1.04 |
| PIPE-code | cost, USD | 1.50 | 1.73 | 1.87 | 1.08 |
| PIPE-code | time, s | 343.3 | 370.0 | 435.8 | 1.18 |
| PIPE-code-app | cost, USD | 6.03 | 6.07 | 8.92 | **1.47** |
| PIPE-code-app | time, s | 666.1 | 872.6 | 941.2 | 1.08 |

Routing time-to-route across 175 runs: median 2.6 s, 90th percentile 3.2 s,
maximum 19.4 s.

**The cost threshold is currently tighter than the noise.**
`cost.median_regression_ratio` is 1.25, and one unchanged build produced a
1.47 spread on the most expensive scenario. On that evidence the cost gate
would fire on noise for `PIPE-code-app` if it were blocking. It is not
blocking — `basis` is `provisional`, so relative findings are reported and
never block — which is exactly why that setting has not yet cost anyone a
false alarm. It must not be switched to blocking at 1.25.

The time threshold of 1.5 sits above the observed time spread (1.18 at worst),
so it is plausible as written.

Caveat on all of the above: three runs, one build, one day, and on a tree that
has since changed. It is enough to reject a threshold as too tight; it is not
enough to declare one calibrated.

## Calibration: what would let the relative half block

`thresholds.json` carries `basis: provisional` and `calibrated_from: null`, and
its protocol asks for repeated `make measure` runs against one unchanged build.
At roughly ten hours and a hundred and fifty dollars per run, that protocol has
never been executed, and on current evidence it never will be.

The cheaper estimator is already collected: each scenario runs three times per
measurement, and `perf_gate.spread()` records `median`, `min`, `max` and `n`
for every metric. The spread across those runs is a within-build noise sample
bought at no extra cost. Two measurements of two different builds also give a
between-build delta for metrics nobody expects to move.

This is a proposal, not the current rule: the current rule is what
`calibration_protocol` says.

## Metric catalogue

Every threshold below is defined in `thresholds.json` under the named key.
"Absolute" means it blocks on the first measurement with no baseline;
"relative" means it is a ratio against a promoted baseline and is inert while
`basis` is `provisional`.

| Metric | Key | Kind | Value | Severity |
|---|---|---|---|---|
| Positive routing accuracy | `reliability.routing_positive_accuracy_floor` | absolute | 1.0 | major |
| Negative routing accuracy | `reliability.routing_negative_accuracy_floor` | absolute | 1.0 | major |
| Control probes | `reliability.routing_control_floor` | absolute | 1.0 | critical |
| Pipeline completion | `reliability.pipeline_completion_floor` | absolute | 1.0 | major |
| Unmeasured runs | `coverage.unmeasured_runs_ceiling` | absolute | 0 | major |
| User-only invocation attempts | `coverage.user_only_attempt_ceiling` | absolute | 0 | minor |
| Unresolved blocking findings | `quality.blocking_findings_rate_ceiling` | absolute | 0.0 | major |
| Cost regression | `cost.median_regression_ratio` | relative | 1.25 | major |
| Time regression | `time.median_regression_ratio` | relative | 1.5 | major |
| Verify iterations | `quality.verify_iterations_median_ceiling_delta` | relative | +1 | major |
| Coverage drop | `quality.coverage_floor_delta` | relative | -2.0 pp | major |

Free-tier floors live in their own commands rather than in `thresholds.json`:
schema-constraint mutation coverage has a 0.9 floor passed on the
`make mutation` command line, and the CLI-tier sweep (`make mutation-cli`)
accepts a `--threshold` but is given none, so it records and never fails.

## What the suite collects and then ignores

Nine signals are recorded on every measured run and read by no threshold.
They are not gaps in the harness — the data is already on disk — they are gaps
in the definitions:

| Signal | Recorded as | Why it matters |
|---|---|---|
| Per-role token and cost split | `runs[].role_usage[]` | The only per-role numbers the suite has. `PERFORMANCE.md` describes them as what lets a cost rise be attributed to the planner, executor, verifier or coordinator. Nothing aggregates them. |
| Coverage target | `runs[].quality.coverage_target` | Recorded next to `coverage_percent` and never compared to it. The PRD's "coverage target met or hard-failed" is one subtraction away. |
| Tests passed | `runs[].quality.tests_passed` | A per-run pass/fail boolean no key reads. |
| Turns | `runs[].turns` | Recorded on every pipeline run, never aggregated. |
| Stop reason | `runs[].stop_reason` | The only field that distinguishes a clean pass from an iteration-cap hit. |
| Skill sequence | `runs[].skills_invoked[]` | The full trail, capped at 60. It would answer "did anything run out of order" and "did an unattended run reach merge-pr". Printed to the console, judged by nothing, absent from the measurement schema. |
| Lane escalations | `code-state.json` `runs[-1].escalations` | `PIPE-code-app` exists to make a high-stakes path trigger an escalation. The harness opens that ledger and reads seven other keys from it. |
| Finding dimension | collapsed at collection | Findings become a severity count, so no per-dimension claim (standards conformance, audience style) can be answered from a measurement. |
| Spread min/max/n | `aggregate.*.{min,max,n}` | Recorded explicitly for calibration, and `calibrated_from` is still null. |

## PRD goal coverage

The PRD carries 39 goals with measurable targets. Most describe the product,
the marketplace or an org rollout, and the eval suite never sees that data.
Of the goals that are statements about pipeline runtime behaviour:

**Gated today** — a threshold reads the number and can fail a release:

- Routing accuracy, positive and negative, and the control probes (G8a).
  Positive routing coverage is 28 of 28 shipped skills, now pinned by
  `runner/test_dataset_integrity.py` rather than asserted in prose.
- Pipeline completion, and cost as a release-over-release ratio (G5).
- Unresolved blocking findings, at a rate ceiling of zero.

**Measured but ungated** — the number exists and nothing judges it:

- Gate integrity (G1) is pinned by 36 deterministic cases in
  `dataset/cases/06-gates.json`, which fail `eval-source`; no tier-3 metric
  counts an escape from a real run's skill trail.
- The verifier's defect-catch rate on the seven seeded fixture defects (G16)
  is measured by `make catch-rate`, which is paid, is not in the release gate,
  and has no threshold.
- Per-dimension verifier findings (G10, G38) are resolvable by
  `make verifier-rates` from an existing workspace, gated by nothing.

**Measurable but not measured** — the harness already opens the data:

- Zero-finding run rate within the iteration cap (G3): needs `stop_reason`,
  which is recorded.
- Coverage target met rather than merely not-regressed (G3): needs
  `coverage_target`, which is recorded.
- Lane escalation on a high-stakes path (G25): needs `escalations`, which sits
  in a ledger the harness already reads.
- Unattended runs stopping before merge (G34): needs `skills_invoked`, which
  is recorded.

**Not measurable by this suite** — would need a real forge, a tracker, a
second runtime or a population of real tickets: reviewable PR size (G4),
portability across runtimes (G6), the e2e merge brake (G13), fast-lane
adoption share (G15), tracker and PR metadata sync (G22), and every org,
marketplace and commercial-adoption goal.

The honest summary: the gate is strong on **reliability** — does the right
skill run, does it finish, does it end clean — and thin on **quality**, where
it currently judges one count and two baseline-relative medians. Every metric
that would deepen the quality half is already being collected.

## Changing a metric

Thresholds live in `thresholds.json` and nowhere else. Add or change one there
with its `value`, `severity`, `rule` and `why`, and a `perf_gate.py` reader if
it is new. `runner/test_dataset_integrity.py` checks that every entry carries
the required fields and that a `calibrated` basis names what it was calibrated
from. Bumping a threshold to blocking without evidence from an observed spread
is what the `basis` field exists to prevent.
