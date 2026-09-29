---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-prd/result.json }
pattern: '"(?:findings|errors)"\s*:\s*\[\s*[{"][\s\S]*\bgh\b'
---

The run has no GitHub access, so `gh pr create` fails. ADR-0088: that failure
is surfaced as a finding (or error) in the result document the post-hook
finalizes, never swallowed. A result.json with empty findings and errors hid
it; a missing result.json means the mandatory Finish never ran.
