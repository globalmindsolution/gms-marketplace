---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/audit-the-repository-for-security-weaknesses-e64d/steps/audit-security/state.json }
pattern: '^(?=[\s\S]*"status"\s*:\s*"completed")(?=[\s\S]*"audit"\s*:\s*"counted from the report)'
---

The Finish ran through the post-hook and the post-hook accepted it: the
invocation is `completed` and `states.audit` was counted from the report's
sections against the template. A report that breaks the template is refused
(exit 1) and leaves the invocation in progress.
