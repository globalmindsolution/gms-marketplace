---
type: file_exists
path: .eval-origin.git/refs/heads/**
exists: false
---

create-pr detects the base with `gh repo view` BEFORE it pushes, and that call
is critical "so its failure now stops the run before the push instead of after
it" (SKILL.md step 1). The local origin stands in for GitHub; a ticket-branch
ref appearing in it means the skill pushed past a failed critical call.
