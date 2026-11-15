---
type: regex
target: { source: file, path: docs/architecture/lld/gift-cards/data/ledger.md }
pattern: '^-{3}(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus: "?deprecated"?\n)(?=(?:(?!\n-{3}\n)[\s\S])*\nversion: 1\n)(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus_reason: "?[^\n]*cut from scope by leadership)'
flags: i
---

`docs/architecture/lld/gift-cards/data/ledger.md` is part of the cut feature: its front matter reads `status:
deprecated` at the unchanged version 1, with the user's reason recorded as
`status_reason` -- which only `acs.py design status --reason` writes. A
deprecation without the reason, or a hand-edited `status:` line, fails here.
