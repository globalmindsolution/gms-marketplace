---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/audit-the-design-against-the-code-9784/steps/audit-design/result.json }
pattern: '^(?=[\s\S]*"audit"\s*:\s*\{)(?=[\s\S]*"unimplemented"\s*:\s*[1-9])(?=[\s\S]*"undocumented"\s*:\s*[1-9])(?=[\s\S]*"drifted"\s*:\s*[1-9])(?=[\s\S]*"planned"\s*:\s*0\b)(?=[\s\S]*"unversioned"\s*:\s*0\b)'
---

The result document's `states.audit` -- rewritten by the post-hook from the
`### ` entries of report.md, whatever the coordinator claimed -- counts each
kind: at least one
unimplemented, undocumented and drifted gap; none `planned`, because every
document is `status: implemented` -- an unimplemented element there is a
regression, never the design ahead of the code; and none `unversioned`,
because every document carries valid front matter. A missing result.json
means the mandatory Finish never ran.
