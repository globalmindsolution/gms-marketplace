---
type: regex
target: { source: file, path: docs/requirements/non-functional/privacy.md }
pattern: '^(?=DRAFT\s*[—–-]+\s*human-confirm-required)(?=[\s\S]*\bMUST\b)(?=[\s\S]*\bEU\b)(?=[\s\S]*\b30\s?days?\b)'
flags: mi
---

The privacy concern is routed to `<non_functional_dir>` as its own item,
DRAFT-marked, carrying EU residency and the 30-day deletion bound.
