---
type: regex
target: { source: file, path: docs/api/customers.md }
pattern: '^(?=[\s\S]*\boffset\b)(?=[\s\S]*\blimit\b)(?=[\s\S]*\b20\b)'
---

Task 1's deliverable (AC-1): the new API page documents both parameters and
the default of 20 per page. The scaffold has no `docs/api/`, so a run that
skipped the partition fails here (a regex on a missing file fails).
