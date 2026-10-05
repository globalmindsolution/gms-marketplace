---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/audit-the-repository-for-security-weaknesses-e64d/steps/audit-security/result.json }
pattern: '"skipped"\s*:\s*\[[^\]]*"threat-model"'
---

result.json's `states.audit.skipped` lists the threat-model slice. A run that
"audited" the code against a container view it mistook for a threat model
lists nothing skipped.
