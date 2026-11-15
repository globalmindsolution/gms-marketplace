---
type: regex
target: { source: file, path: docs/architecture/hld/tech-stack.md }
pattern: '^-{3}\nstatus: "implemented"\nversion: 1\ntickets:\n  - "EVAL-1"\n-{3}\n\n# Tech stack\n\n## Languages\n\nPython 3\.\n\n## Frameworks\n\npytest\.\n\n## Conventions\n\nsrc layout: one package per container under src/\.\n(?![\s\S])'
---

Read-only, including the one HLD document with no gap: its front matter
(`status`, `version`, `tickets`) is not re-stamped or bumped by an audit
that only read it.
