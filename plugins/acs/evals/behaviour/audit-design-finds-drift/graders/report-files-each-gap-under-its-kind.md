---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/audit-the-design-against-the-code-9784/steps/audit-design/iter-1/report.md }
pattern: '^(?=[\s\S]*^## Unimplemented[^\n]*\n(?:(?!\n## )[\s\S])*?^### [^\n]*notifier)(?=[\s\S]*^## Undocumented[^\n]*\n(?:(?!\n## )[\s\S])*?^### [^\n]*orders)(?=[\s\S]*^## Drifted[^\n]*\n(?:(?!\n## )[\s\S])*?^### (?:(?!\n## )[\s\S])*?(?:\b50\b(?:(?!\n## )[\s\S])*\b20\b|\b20\b(?:(?!\n## )[\s\S])*\b50\b))'
flags: mi
---

Each gap is one `### ` entry under its kind, because those entries ARE the
counts: the post-hook counts them into `states.audit`. The notifier is under
`## Unimplemented` (its documents are implemented, so not Planned), the orders
API under `## Undocumented`, and the page size under `## Drifted` with both
readings, 50 and 20.
