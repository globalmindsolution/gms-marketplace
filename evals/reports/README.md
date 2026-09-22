# Release-gate reports

The reviewed evidence for each gated release, promoted here from
`results/report.*` once the run is signed off.

`results/` is working output and gitignored; these are the record.

The verdict follows [`../docs/RUBRIC.md`](../docs/RUBRIC.md): severity decides, not the raw pass count.

| Report | Build under test | Result |
|---|---|---|
| [`acs-v0.4.10-gate.md`](acs-v0.4.10-gate.md) | acs `0.4.9` (the pre-`v0.4.10` unreleased tree) | PASSED — 337/337, 0 critical / 0 major / 0 minor failures, 55.0% schema constraint coverage |

Regenerate with `make gate`, then copy `results/report.md` and
`results/report.html` here under the release's name.
