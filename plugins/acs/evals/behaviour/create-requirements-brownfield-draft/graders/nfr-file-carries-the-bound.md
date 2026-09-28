---
type: regex
target: { source: file, path: docs/requirements/non-functional/performance.md }
pattern: '^(?=[\s\S]*^DRAFT\s*[—–-]+\s*human-confirm-required)(?=[\s\S]*300\s?ms)'
flags: m
---

The non-functional item is routed to `<non_functional_dir>`, marked DRAFT,
and states the PRD's latency bound.
