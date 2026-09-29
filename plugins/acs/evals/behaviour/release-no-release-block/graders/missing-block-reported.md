---
type: regex
target: last_message
pattern: 'release[`"'']?\s+(?:block|key|section|config)|no\s+[`"'']?release'
flags: i
---

The reply names the cause: `.acs/settings.json` has no release block, so
/acs:release cannot run here. A run that stopped silently, or cut the release,
says neither.
