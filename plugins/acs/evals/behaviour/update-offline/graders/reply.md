---
type: llm
---

PASS if the final reply states the installed acs version, says the latest
released version could not be determined because GitHub was unreachable (or
`gh` unauthenticated), and gives the commands to check and refresh manually.
FAIL if it claims the plugin is up to date, names a "latest" version it did
not fetch, says the marketplace was refreshed or the plugin updated, or asks
the user a question.
