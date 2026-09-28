---
type: regex
target: { source: file, path: docs/product/prd.md }
pattern: '^(?=[\s\S]*\b500\b)(?=[\s\S]*\b5\s?%)(?=[\s\S]*\b2\s?s\b|[\s\S]*\b2\s?seconds?\b)(?=[\s\S]*99\.5\s?%)(?=[\s\S]*GDPR)(?=[\s\S]*\bWon.?t\b)'
flags: i
---

Greenfield has no code to reverse-engineer, so every fact comes from the
elicited answers: the two goal metrics (500 bookings a week, under 5%
no-shows), the NFRs (2 s p95, 99.5%), the GDPR constraint and a MoSCoW
Won't bucket. None of them is anywhere in the repo.
