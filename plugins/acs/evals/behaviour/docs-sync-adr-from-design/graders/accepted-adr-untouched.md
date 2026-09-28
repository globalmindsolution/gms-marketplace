---
type: regex
target: { source: file, path: docs/adr/0002-serve-http-with-stdlib-wsgi.md }
pattern: '^# 2\. Serve HTTP with the stdlib WSGI interface\n\nDate: 2026-07-14\n\n## Status\n\nAccepted\n\n## Context\n\nshop is a small service and should run anywhere Python runs\.\n\n## Decision\n\nThe HTTP front is a plain WSGI app built on the standard library only\.\n\n## Consequences\n\nNo web framework dependency; routing is hand-written in src/shop/web\.py\.\n$'
---

ADR 0001's own rule: an accepted ADR is never edited. The new decision does
not supersede 0002 (sqlite3 is stdlib too), so 0002 stays byte-for-byte as
committed.
