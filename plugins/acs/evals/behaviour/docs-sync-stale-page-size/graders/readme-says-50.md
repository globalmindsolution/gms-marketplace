---
type: regex
target: { source: file, path: README.md }
pattern: '\b50\b[^\n]*per page|per page[^\n]*\b50\b'
---

The stale sentence now carries the new default. A `{source: file}` regex reads
the file's final contents, so it sees a modification (which `files` would not).
