---
type: regex
target: last_message
pattern: 're-?approv|unapproved|not approved|approval|different revision|edited'
flags: i
---

The run stops and says why: the plan on disk is not the plan that was
approved. A run that fired the skill and ended silently, or reported a
success, says none of this.
