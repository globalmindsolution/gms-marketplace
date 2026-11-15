---
type: regex
target: { source: file, path: docs/architecture/lld/flows/nightly-export.md }
pattern: '^# nightly-export\n\n```mermaid\nsequenceDiagram\n  participant cron\n  participant export-worker\n  participant Redis\n  cron->>export-worker: run\n  export-worker->>Redis: RPUSH exports\n```\n(?![\s\S])'
---

Even a flow the shift made stale is not this skill's to delete: the
nightly-export LLD file stays, byte for byte. Retiring it is a per-ticket
design decision (ADR-0118); the re-run regenerates the HLD only. A missing
file fails this grader, so deleting the flow is caught as surely as editing
it.
