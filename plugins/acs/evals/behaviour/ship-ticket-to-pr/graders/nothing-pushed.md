---
type: file_exists
path: .eval-origin.git/refs/heads/**
exists: false
---

create-pr detects the base with gh BEFORE pushing, and that critical call
fails here, so the ticket branch never reaches the local origin (the
stand-in for GitHub).
