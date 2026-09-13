# Baselines

One promoted measurement per gated release: `acs-<version>.json`, conforming to
[`../measurement.schema.json`](../measurement.schema.json). A run scoped to the
cheap half (`make measure-routing`) may be promoted as `acs-<version>-routing.json`
— the gate then compares routing probes against it and nothing else, says so
in its verdict, and a full `acs-<version>.json` supersedes it (it sorts later,
and `pick_baseline` takes the newest).

A baseline is not a separate artifact — it is `results/measurements.json` from a
run that was reviewed and kept, exactly as `reports/` holds a promoted report.

Promote one only when all three hold:

- the measurement is **not** marked `incomplete` — it finished what its
  `scope` set out to measure (a probe filter, or a probe with no runs, marks it
  incomplete; a routing-only run that finished does not),
- its `scenario_set_version` matches the current `../scenarios.json` (a changed
  experiment makes older numbers incomparable, and `perf_gate.py` refuses to
  compare across the boundary rather than pretending),
- the run's findings were triaged — a baseline recorded from a build with a
  known regression bakes that regression in as the thing to beat.

**Current contents.** `acs-0.4.9-routing.json` — the first routing-scoped
baseline, taken 2026-09-10 against the installed 0.4.9 build (= `main` at
`9332f22`): 30 probes × 5 runs, all 30 unanimous, pre-flight and all three
controls clean, median time-to-route 3.0 s across the 23 description probes.
It was composed twice, and the document's `scope_note` and `triage` say so:
for scenario set 1.3.0 from the 1.2.0 run plus five fresh runs of `ROUTE-ship`
under its corrected prompt, then for 1.5.0 with five fresh runs each of
`ROUTE-create-requirements` (on the fixture app, 5/5, 5.2 s median) and
`ROUTE-docs-sync` (on the ticketed fixture app with a committed change on the
ticket branch, 5/5, 4.1 s median) — the two probes that split 4/5 under 1.3.0
because the seeded sandbox made their prompts false, first mis-triaged as
description defects. Reliability is an absolute gate, so a baseline is never
promoted with a split baked in. No pipeline-scoped or full baseline exists yet:
cost, verify-iteration and coverage comparisons still report UNCOMPARED — see
[`../../docs/PERFORMANCE.md`](../../docs/PERFORMANCE.md).
