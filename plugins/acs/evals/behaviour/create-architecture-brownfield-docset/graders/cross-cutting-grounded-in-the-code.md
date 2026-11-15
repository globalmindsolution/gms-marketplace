---
type: regex
target: { source: file, path: docs/architecture/hld/cross-cutting.md }
pattern: '^(?=[\s\S]*^#{2,3} +API conventions)(?=[\s\S]*^#{2,3} +Data conventions)(?=[\s\S]*^#{2,3} +Security)(?=[\s\S]*^#{2,3} +Observability)(?=[\s\S]*\boffset\b)(?=[\s\S]*\blimit\b)'
flags: mi
---

`hld/cross-cutting.md` is always written and carries its required sections
(API conventions; Data conventions; Security; Observability). Its API
conventions state the pagination the code actually uses -- `offset`/`limit`
on GET /customers -- rather than a generic convention the code does not
follow.
