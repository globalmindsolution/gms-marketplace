# /acs:analyze-requirements — reuse, when a previous analysis exists

Open this when `artifacts show` reports a previous analysis of this subject
(`<previous_analysis>`) or a Development run has the feature's living
analysis (`<feature_analysis>`): the coordinator names it in every survey
lane's `<inputs>`, and every lane starts from it. A
first analysis reads none of it.

## What the survey does with it

The feature's living analysis is the feature as a whole; a Development run
narrows it to this change and cites what it carries over. The impact lanes
re-verify each of its impact-map rows against the current code —
still true / changed / gone, each with the evidence — the requirements lane
carries forward its answered `C-n` entries (answers are never asked again),
and both record what changed since under a `## Changes since the last
analysis` section of the notes. An answer the previous analysis records but
the ledger lacks (a fresh workspace) is still a recorded answer: re-record it
verbatim with `clarify.py add … --answer` in Stage 2 rather than asking it
again.

### Reuse — when a previous analysis exists

For the analyst's requirements lane:

When `<inputs>` names the previously published analysis (its `README.md` and
context files, or a legacy single `analysis.md`), it is where the survey
starts, not an answer key:

- Its impact-map rows are re-verified by the impact lanes — still true /
  changed / gone; you re-verify its problem statement and criteria the same
  way, each with the evidence you opened now.
- Carry forward its answered `C-n` entries: they are answers, never questions
  again. Name any the ledger (`clarify.py list`) lacks, so the
  coordinator re-records them instead of asking.
- Record what changed since under a `## Changes since the last analysis`
  section of the notes: criteria the requirements have gained or lost;
  questions answered since and questions newly raised.
- The feature's living analysis (a Development run's second reuse input) is
  the whole feature: carry over only what bears on THIS change, cite it, and
  re-verify it like any other previous analysis.
