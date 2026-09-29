---
type: regex
target: { source: file, path: pyproject.toml }
pattern: 'fail[_-]under\s*=\s*"?90\b'
---

The coverage tooling fails the run below the 90% target the prompt relayed.
