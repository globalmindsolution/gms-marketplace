---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/regenerate-the-architecture-after-the-shift-1304/steps/create-architecture/iter-1/gaps.md }
pattern: '^(?=[\s\S]*## Unimplemented\n(?:(?!\n## )[\s\S])*(?:export.worker|redis))(?=[\s\S]*## Undocumented\n(?:(?!\n## )[\s\S])*\borders\b)'
flags: i
---

The existing HLD drifts from the code, so the re-run must not rewrite it
blind: the gap analysts run beside the survey and their notes are joined
into `iter-1/gaps.md` (ADR-0122). That report files the removed export
worker / Redis queue under Unimplemented (designed, no longer built) and the
new orders API under Undocumented (built, not designed). A run that skipped
the gap analysis has no such file, and a missing file fails this grader.
