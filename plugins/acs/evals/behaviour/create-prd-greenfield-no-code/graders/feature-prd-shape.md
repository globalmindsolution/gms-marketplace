---
type: regex
target: { source: file, path: docs/product/features/online-booking/prd.md }
pattern: '^(?=[\s\S]*^#{1,3}\s+Summary[\s\S]*^#{1,3}\s+Goals served[\s\S]*^#{1,3}\s+Requirements[\s\S]*\*\*R1\*\*[\s\S]*^#{1,3}\s+Acceptance criteria[\s\S]*^#{1,3}\s+Dependencies[\s\S]*^#{1,3}\s+Out of scope)(?=[\s\S]*\bG1\b)'
flags: mi
---

A feature PRD carries EXACTLY the six sections the author is told to write, in
order, with requirement ids (`**R1**`, ...) and the goal id the prompt gave the
feature (online booking serves G1).
