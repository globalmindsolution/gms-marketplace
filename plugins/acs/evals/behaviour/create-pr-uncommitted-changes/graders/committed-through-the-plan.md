---
type: tool_used
tool: Bash
input_match: 'acs\.py(?:\\?")?\s+pr\s+commit\s+--plan\b'
min: 1
---

The commits are made by the plugin's own CLI from the confirmed plan (step C4),
the only commit path create-pr has. A run that stopped at "uncommitted changes"
-- create-pr's old rule -- never calls it.
