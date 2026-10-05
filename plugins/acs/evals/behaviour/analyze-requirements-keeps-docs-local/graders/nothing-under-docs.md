---
type: regex
target: files
pattern: '^docs/'
flags: m
match: not_contains
---

A saved "keep local" default is followed silently: no Development folder is
created and no document is published into the repo. A run that published to
`docs/development/` anyway -- or mirrored the analysis there -- fails here.
