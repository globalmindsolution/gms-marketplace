---
type: file_exists
path: .eval-origin.git/refs/heads/**
exists: false
---

create-pr detects the base with gh BEFORE pushing, and that critical call
fails here, so no branch reaches the local origin.
