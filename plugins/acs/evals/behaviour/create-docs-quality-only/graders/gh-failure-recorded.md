---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-docs/result.json }
pattern: '"(?:findings|errors)"\s*:\s*\[\s*[{"][\s\S]*\bgh\b'
---

ADR-0088: the failed `gh pr create` is surfaced as a finding (or error) in
the set's result document, never swallowed. A missing result.json means the
mandatory per-set Finish never ran.
