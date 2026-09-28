---
type: regex
target: { source: file, path: docs/operations/release-process.md }
pattern: '^(?=[\s\S]*CHANGELOG\.md)#{1,3}\s+Versioning and release-cut steps[\s\S]*^#{1,3}\s+Changelog discipline[\s\S]*^#{1,3}\s+Branch and tag conventions[\s\S]*^#{1,3}\s+Rollback procedure'
flags: m
---

The set's sentinel file carries the four sections `DOC_SETS["operations"]`
requires, in order, and is tailored: it names `CHANGELOG.md`, the file the
request said every change adds a line to. The template says only "where the
changelog lives".
