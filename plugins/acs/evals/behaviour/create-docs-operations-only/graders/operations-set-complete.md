---
type: regex
target: files
pattern: '^(?=[\s\S]*^docs/operations/release-process\.md$)(?=[\s\S]*^docs/operations/runbooks\.md$)(?=[\s\S]*^docs/operations/observability\.md$)(?=[\s\S]*^docs/operations/incident-response\.md$)(?=[\s\S]*^docs/operations/test-scheduling\.md$)'
flags: m
---

The Output contract: EXACTLY the five files `DOC_SETS["operations"]` lists,
created by this run at the set's default location (no operations set
existed, so its location is `docs/operations`).
