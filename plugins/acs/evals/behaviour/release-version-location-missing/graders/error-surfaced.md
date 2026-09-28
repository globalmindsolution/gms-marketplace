---
type: regex
target: last_message
pattern: 'package\.json'
---

The status call's `error` is surfaced verbatim ("cannot read …/package.json:
… No such file or directory"), so the reply names the missing file. A run that
stopped silently, or blamed gh, does not.
