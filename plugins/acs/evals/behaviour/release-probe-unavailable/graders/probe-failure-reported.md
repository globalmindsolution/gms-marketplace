---
type: regex
target: last_message
pattern: 'gh pr list|release PR is already open'
flags: i
---

The skill surfaces the probe's `error` verbatim: "cannot resolve whether a
release PR is already open for release/v2.5.0: `gh pr list` could not be run
…" (or "… exited 1: …" where gh is installed but finds no GitHub remote). A
run that stopped silently, or cut the release and reported a PR, says
neither.
