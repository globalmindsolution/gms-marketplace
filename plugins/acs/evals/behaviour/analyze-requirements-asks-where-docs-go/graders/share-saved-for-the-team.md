---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"share_run_documents"\s*:\s*true'
---

"Save it for the whole team" is the `team` scope: `acs.py docs decide --share
yes --scope team` merges `docs.share_run_documents: true` into the committed
`.acs/settings.json`, so the question is never asked again in this repo.
