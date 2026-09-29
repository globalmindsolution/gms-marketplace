---
type: regex
target: { source: file, path: docs/standards/coding-standards.md }
pattern: '^(?=[\s\S]*ValueError)#{1,3}\s+Language and style conventions[\s\S]*^#{1,3}\s+Error handling[\s\S]*^#{1,3}\s+Testing conventions'
flags: m
---

standards reads the principles set when it exists (the altitude gradient
architecture -> principles -> standards). The `ValueError` rule appears only
in docs/principles/principles.md, never in the request or the template, so
coding-standards.md carrying it -- beside its three required sections, in
order -- shows the principle was realized as a standard.
