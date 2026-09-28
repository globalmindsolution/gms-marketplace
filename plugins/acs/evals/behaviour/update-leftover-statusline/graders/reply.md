---
type: llm
---

PASS if the final reply states the installed acs version, says the latest
release could not be determined because GitHub was unreachable (or `gh`
unauthenticated), gives the commands to check and refresh manually, and --
if it mentions the status line at all -- tells the user to remove the
`statusLine` entry from `.claude/settings.json` themselves rather than
saying it was removed.
FAIL if it claims the plugin is up to date, names a latest version it did
not fetch, says it edited or cleaned up any settings file, or asks the user
a question.
