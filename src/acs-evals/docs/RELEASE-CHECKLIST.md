# Release checklist — cutting an `acs` version

The evaluation steps that belong in an `acs` release cut, in order. Full
process and triage rules: [`EVALUATION-PROCESS.md`](EVALUATION-PROCESS.md).

Copy this into the release PR and tick it.

## Before the version bump

- [ ] **Working tree is green.** The code being released behaves as recorded.

      ```bash
      cd src/acs-evals
      export ACS_PLUGIN_ROOT=$PWD/../../plugins/acs
      make gate
      ```

- [ ] **No `critical` or `major` failures.** Per [`RUBRIC.md`](RUBRIC.md) the
      gate exits non-zero on either. `minor` drift does not block, but each one
      is triaged to a decision here rather than carried to the next cut.

- [ ] **Every failure is resolved**, each to one of the three outcomes —
      regression fixed, golden re-recorded in its own reviewed commit, or case
      corrected as a dataset bug.

- [ ] **Coverage has not regressed** (`make mutation`, floor 90%). A re-recording
      that keeps the case count but lowers coverage has weakened the gate.

- [ ] **Every known divergence has a decision.** Read the report's *Known
      divergences* section. For each: fixed in this release, or accepted and
      named in the changelog. An undecided divergence blocks the cut.

- [ ] **New surfaces have cases.** Anything in this release's changelog that
      added an observable surface — a CLI subcommand, a schema, a gate, a
      skill — has at least one case pinning it. If not, add it now; that is
      cheaper than finding out from a consumer.

- [ ] **The generated eval tree is in sync** (`make check`, included in
      `make gate`).

- [ ] **Skill performance is measured, not assumed** (`make measure`, then
      `make perf` — both included in `make gate`).

      ```bash
      make measure-plan     # what it will run and how many sessions, free
      make measure          # SPENDS MONEY; needs `claude` on PATH
      ```

      Tier 3 answers the four questions tier 1 cannot: did skills get less
      reliable, worse, more expensive, or slower. **UNMEASURED is a failing
      state**, not a pass — see [`PERFORMANCE.md`](PERFORMANCE.md). If the
      measurement cannot be taken for this cut, say so in the release notes
      rather than letting a green tier-1 report imply it.

- [ ] **Every absolute floor held.** Routing accuracy, run completion, and
      no run finishing with an unresolved blocking finding. These block
      regardless of calibration. A negative routing probe that auto-invoked is
      `critical` and stops the cut outright.

- [ ] **Relative findings triaged.** While thresholds are provisional these do
      not block, but each cost, time, iteration or coverage regression gets a
      decision: accepted and named in the changelog, or fixed.

## At the version bump

- [ ] **Promote the measurement to a baseline.** Copy
      `results/measurements.json` to `dataset/baselines/acs-<version>.json` —
      but only if it is not marked `incomplete` and its findings were triaged.
      A baseline recorded from a build with a known regression bakes that
      regression in as the thing to beat.

- [ ] **Re-baseline the dataset.** Set `recorded_against` in
      `dataset/manifest.json` to the version being released, and clear
      `recorded_against_note` if it no longer applies. Otherwise every later
      run prints an off-baseline warning and the gate's verdict softens to
      "PASSED (off-baseline)".

- [ ] **Bump `dataset_version`** if cases changed in this cycle. Patch for
      added cases, minor for a changed case format, major for a runner
      contract change.

- [ ] **Re-run the gate** after re-baselining, so the committed report matches
      the released version.

## After publishing

- [ ] **Install the published build and run the gate against it** — with
      `ACS_PLUGIN_ROOT` **unset**, so the runner resolves the installed
      plugin rather than the source tree:

      ```bash
      claude plugin install acs@gms-marketplace
      unset ACS_PLUGIN_ROOT
      make gate
      ```

      This is the only step that catches **packaging drift** — a file that
      exists in the source tree but never reaches the published plugin. A
      source-tree run cannot see it.

- [ ] **Attach `results/report.md`** to the release PR or the GitHub release
      notes.

- [ ] **Tag the dataset** at the state that gated this release, so the
      evidence is recoverable later:

      ```bash
      git tag -a acs-v0.4.10-gate -m "Dataset state that gated acs v0.4.10"
      git push origin acs-v0.4.10-gate
      ```

## Not covered by this checklist

Tier 2, the `claude plugin eval` routing tree in `evals/`, has still never been
executed — it needs early access. It is now **redundant for gating**: tier 3
measures routing from the same `dataset/routing.json` prompts through plain
`claude -p`, with a stated decision rule. Keep tier 2 for the day the feature
opens up; do not treat its absence as a hole any more.

What remains genuinely uncovered: how acs behaves on **real tickets**. Tier 3's
pipeline scenarios run in a throwaway sandbox on a trivial change, so its cost
and quality numbers are useful as release-over-release deltas and not as an
estimate of what a consumer's ticket costs. See the limitations in
[`PERFORMANCE.md`](PERFORMANCE.md).
