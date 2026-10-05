---
type: file_exists
path: .eval-origin.git/refs/heads/**
exists: false
---

Nothing is pushed: the commit phase is local, and base detection -- critical,
and run before the push -- fails, so the new branch stays on the local
checkout for a re-run to push.
