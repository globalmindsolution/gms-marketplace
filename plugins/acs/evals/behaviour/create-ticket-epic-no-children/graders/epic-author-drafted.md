---
type: tool_used
tool: Agent
input_match: '"subagent_type"\s*:\s*"[^"]*create-ticket-epic-author"'
min: 1
---

The draft comes from the author for the chosen type (ADR-0138): an epic is
drafted by `create-ticket-epic-author`, spawned under its plugin name or the
generated `acs-create-ticket-epic-author` copy, before the reviewer judges it.
