---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements/local/analysis.md }
pattern: '^-{3}\n(?:[a-z_]+:[^\n]*\n)*api_surface:[ \t]*true[ \t]*\n(?:[a-z_]+:[^\n]*\n)*-{3}'
---

The local analysis is what `ship.yaml`'s `api_surface_changed` predicate and
the `/acs:create-api-contract` gate read (`artifacts show` finds it in the run
folder), so its front matter must still declare the API surface.
