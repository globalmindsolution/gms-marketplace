---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements/local/analysis/README.md }
pattern: '^-{3}\n(?:[a-z_]+:[^\n]*\n)*ready_for_planning:[ \t]*true[ \t]*\n(?:[a-z_]+:[^\n]*\n)*-{3}'
---

The local analysis is what `/acs:create-impl-plan` reads (`artifacts show`
finds it in the run folder), so its front matter must still carry the
machine-read verdict, `ready_for_planning: true` -- every question was
answered up front.
