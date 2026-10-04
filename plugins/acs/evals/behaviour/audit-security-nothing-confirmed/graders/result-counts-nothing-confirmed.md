---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/audit-the-repository-for-security-weaknesses-e64d/steps/audit-security/result.json }
pattern: '^(?=[\s\S]*"audit"\s*:\s*\{)(?=[\s\S]*"critical"\s*:\s*0\b)(?=[\s\S]*"high"\s*:\s*0\b)(?=[\s\S]*"medium"\s*:\s*0\b)(?=[\s\S]*"low"\s*:\s*0\b)'
---

The repository has no exploitable weakness, no secret and no dependency, so
nothing is confirmed at any severity. The counts are the post-hook's, derived
from the report's `### ` entries, so a false positive the coordinator kept in
a severity section shows up here whatever result.json first claimed.
