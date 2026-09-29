---
type: regex
target: { source: file, path: docs/standards/coding-standards.md }
pattern: '^(?=[\s\S]*ValueError)#{1,3}\s+Language and style conventions[\s\S]*^#{1,3}\s+Error handling[\s\S]*^#{1,3}\s+Testing conventions'
flags: m
---

The sentinel file carries its three required sections in order and states the
confirmed error rule (`ValueError` for bad input). The template names no
exception type.
