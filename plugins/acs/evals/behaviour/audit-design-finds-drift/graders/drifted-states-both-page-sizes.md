---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/audit-the-design-against-the-code-9784/steps/audit-design/iter-1/gaps.md }
pattern: '## Drifted\n(?:(?!\n## )[\s\S])*?(?:\b50\b(?:(?!\n## )[\s\S])*\b20\b|\b20\b(?:(?!\n## )[\s\S])*\b50\b)'
---

The customer listing is in both and they disagree: lld/customer-listing/api/
customers.md says `limit` defaults to 50, src/shop/__init__.py's PAGE_SIZE
is 20. A drifted entry states both readings, so both numbers appear under
`## Drifted` -- a run that filed it as unimplemented, or quietly took one
side, fails.
