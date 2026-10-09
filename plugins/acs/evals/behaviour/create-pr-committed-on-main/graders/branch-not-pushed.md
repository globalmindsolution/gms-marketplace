---
type: file_exists
path: .eval-origin.git/refs/heads/**
exists: false
---

The default-branch read is a critical GitHub call, and a critical call with no
working route stops the run before anything is pushed (SKILL.md, "What to do").
The local origin stands in for GitHub; a ticket-branch ref appearing in it means
the skill pushed past a failed critical call.
