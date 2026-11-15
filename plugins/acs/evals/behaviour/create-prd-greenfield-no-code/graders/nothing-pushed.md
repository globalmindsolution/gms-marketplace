---
type: file_exists
path: .eval-origin.git/refs/heads/**
exists: false
---

The local origin stands in for GitHub and accepts pushes. A new branch ref
appearing in it means the run pushed, which only `/acs:create-pr` does
(ADR-0127).
