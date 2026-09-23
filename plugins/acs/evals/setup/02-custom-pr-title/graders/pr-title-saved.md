---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"pr_title"\s*:\s*"\[\{ticket_(id|ref)\}\] \{title\}"'
---

The one format the user changed is saved, with the ticket id (or the tracker
reference) in brackets ahead of the title.
