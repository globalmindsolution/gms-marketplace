---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/audit-the-security-of-the-repository-abb3/steps/audit-security/result.json }
pattern: '^(?=[\s\S]*"audit"\s*:\s*\{)(?=[\s\S]*"(?:critical|high)"\s*:\s*[1-9])(?=[\s\S]*"refuted"\s*:\s*\d)(?=[\s\S]*"skipped"\s*:\s*\[[^\]]*"threat-model")'
---

result.json's `states.audit` -- rewritten by the post-hook from the report's
`### ` entries -- counts at least one critical or high finding, carries the
`refuted` count, and lists threat-model as skipped (there is no architecture
set). A missing result.json means the mandatory Finish never ran.
