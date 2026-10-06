---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"children"\s*:\s*\[\s*"EVAL-2"\s*,\s*"EVAL-3"\s*,\s*"EVAL-4"\s*\]'
---

`new-ticket.py --parent EVAL-1` writes both link directions, so the converted
epic lists exactly the three minted ids. A run that minted a fresh parent
instead of converting EVAL-1 shifts or loses them.
