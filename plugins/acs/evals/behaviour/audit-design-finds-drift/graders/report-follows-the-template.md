---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/audit-the-design-against-the-code-9784/steps/audit-design/iter-1/report.md }
pattern: '^## Scope[ \t]*\n[\s\S]*^## Summary[ \t]*\n[\s\S]*^## Unimplemented[ \t]*\n[\s\S]*^## Planned[ \t]*\n[\s\S]*^## Undocumented[ \t]*\n[\s\S]*^## Drifted[ \t]*\n[\s\S]*^## Unversioned[ \t]*\n[\s\S]*^## Unverified[ \t]*\n[\s\S]*^## Tickets[ \t]*$'
flags: m
---

Beside the joined gap notes, the audit writes its report from
templates/audit-design-report.md: every `## ` section the template has, in
its order -- the contract the post-hook checks. Leaving out the sections it
had nothing for (Planned, Unversioned) breaks it; an empty section says
`_None._`. No report at all fails too: a regex on a missing file fails.
