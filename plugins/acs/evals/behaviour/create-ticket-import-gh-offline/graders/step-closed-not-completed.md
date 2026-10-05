---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-ticket/state.json }
pattern: '"status"\s*:\s*"(?:failed|interrupted)"'
---

The mandatory Finish runs "also on failure": result.json records the blocked
import (status `failed` with a blocking finding, or `interrupted`) and the
post-hook finalizes it. A step left `in_progress` skipped Finish; one
recorded `completed` claimed an import that never happened.
