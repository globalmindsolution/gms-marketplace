# Quality

**The verify phase of the lifecycle — HOW correctness is assured.** Where
[`requirements/`](../requirements/) defines the behavior that must hold, this set
defines how that behavior is *checked*: the test strategy, what each layer
covers, and the policy that gates a release.

| Doc | What it holds | Status |
|-----|---------------|--------|
| [testing-strategy.md](testing-strategy.md) | The layered test pyramid (contract → deterministic → static → free/paid evals → runtime verifier → dogfooding), the per-skill coverage matrix, principles, and the roadmap to close the gap | ✅ |
| `test-plan.md` | Concrete per-area test plans and the pre-release checklist (currently inline in the [root README](../../README.md#releasing--updating) and [src/acs-evals/behavioural/README.md](../../src/acs-evals/behavioural/README.md)) | planned |
| [skill-rubric.md](skill-rubric.md) | How good a skill is — the six dimensions (routing, gate, contract, structure, recovery, prose), the rule that an unmeasured dimension is not a pass, and the per-skill Ready/Thin/Blocked verdict. The judgement the eval dataset deliberately refuses to make | ✅ |
| [behavioural-eval-rubric.md](behavioural-eval-rubric.md) | What an artifact-level eval must assert to count as evidence — read the workspace not the transcript, shape AND value, an honest tier, real preconditions — plus the severity scale and the order to write the remaining 29 in | ✅ |
| [evaluation-metrics.md](evaluation-metrics.md) | What a release is judged by: the five commands `release.pre_release_gate` runs and in which order, the metric catalogue with each threshold's key in `thresholds.json`, the observed run-to-run variance that says which thresholds are too tight to ever block, and which PRD goals the suite does and does not cover | ✅ |
| [coverage-policy.md](coverage-policy.md) | The 90% coverage floor and its hard-fail rule, the `.coveragerc` exclusions, and the repo-wide gate — `coverage report --fail-under=$ACS_COVERAGE` over the whole measured `source` tree | ✅ |

Verification flows from the layers above it: a `quality/` claim ("create-ticket
is behaviorally covered") must trace to a real check in
[`tests/`](../../tests/) or the [eval harness](../../src/acs-evals/behavioural/README.md). Assert on
artifacts, never on prose.
