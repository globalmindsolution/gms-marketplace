---
type: regex
target: { source: file, path: docs/product/features/wishlist/analysis.md }
pattern: '^-{3}(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus: "?approved"?\n)(?=(?:(?!\n-{3}\n)[\s\S])*\nversion: 2\n)(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus_by: "?eval)(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus_at: )'
---

The wishlist analysis's front matter reads `status: approved` at the SAME
version 2 -- a status move never bumps -- with who (`status_by`, the git
identity `eval <eval@example.com>` when no `--by` is given) and when
(`status_at`) recorded. Only `acs.py design status` writes that pair; a
hand-edited `status:` line carries neither, and a `design bump` shows
version 3 and `proposed`.
