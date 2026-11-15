---
type: file_exists
path: .eval-origin.git/refs/heads/**
exists: false
---

The handoff travels on `refs/acs/handoff/<ID>`, never on a branch (ADR-0131);
a new branch ref on the stand-in origin means the run pushed the work the
way only `/acs:create-pr` may (ADR-0127).
