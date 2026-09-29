---
type: regex
target: { source: file, path: docs/operations/test-scheduling.md }
pattern: '^(?=[\s\S]*^#{1,3}\s+Example cron/CI snippets)(?=[\s\S]*\b0?2:00\b|[\s\S]*\b0 2 \* \* \*)'
flags: m
---

The scheduling recipe is this repo's: the nightly 02:00 UTC run the request
fixed, written as a time or as its cron expression (`0 2 * * *`).
