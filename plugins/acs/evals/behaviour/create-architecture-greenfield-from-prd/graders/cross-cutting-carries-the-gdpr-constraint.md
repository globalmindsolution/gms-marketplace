---
type: regex
target: { source: file, path: docs/architecture/hld/cross-cutting.md }
pattern: '^(?=[\s\S]*^#{2,3} +API conventions)(?=[\s\S]*^#{2,3} +Data conventions)(?=[\s\S]*^#{2,3} +Security)(?=[\s\S]*^#{2,3} +Observability)(?=[\s\S]*\b(?:GDPR|EU)\b)'
flags: m
---

`hld/cross-cutting.md` is always written and carries its required sections
(API conventions; Data conventions; Security; Observability), designed to the
PRD: the conventions every feature follows keep personal data in the EU
under GDPR, the constraint the PRD fixes.
