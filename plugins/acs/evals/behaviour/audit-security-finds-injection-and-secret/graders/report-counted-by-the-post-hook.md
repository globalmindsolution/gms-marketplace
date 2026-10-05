---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/audit-the-security-of-the-repository-abb3/steps/audit-security/state.json }
pattern: '^(?=[\s\S]*"status"\s*:\s*"completed")(?=[\s\S]*"audit"\s*:\s*"counted from the report)'
---

The Finish ran through the post-hook and the post-hook ACCEPTED it: the
invocation is `completed` and its derived states record that `states.audit`
was counted from the report's sections against the template. A completed
result with no report, or with a report that breaks the template, is refused
(exit 1) and leaves the invocation in progress, so the counts in result.json
would be only what the coordinator claimed.
