---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-ticket/state.json }
pattern: '^(?![\s\S]*"status"\s*:\s*"completed")[\s\S]*"status"\s*:\s*"failed"'
---

The run went through Finish and recorded `failed`: a wishlist is a story, a
story links the PRD, and there is none. A completed run means a ticket was
minted for it anyway -- as an unlinked task, say; the post-hook refuses a
completed story with no link, so that is the only way to complete.
