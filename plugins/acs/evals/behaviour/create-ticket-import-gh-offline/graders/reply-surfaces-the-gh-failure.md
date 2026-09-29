---
type: regex
target: last_message
pattern: '\bgh\b[^\n]*(?:fail|not found|not installed|unavailable|could not|cannot|error|auth)|(?:fail|not found|not installed|unavailable|could not|cannot|error)[^\n]*\bgh\b'
flags: i
---

The critical-class failure is surfaced to the user: gh's error, verbatim, with
the canonical hint -- not a silent stop and not a success report.
