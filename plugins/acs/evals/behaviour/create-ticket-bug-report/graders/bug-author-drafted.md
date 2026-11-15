---
type: tool_used
tool: Agent
input_match: '"subagent_type"\s*:\s*"[^"]*create-ticket-bug-author"'
min: 1
---

A bug is drafted by the bug author (ADR-0138), spawned under its plugin name
or the generated `acs-create-ticket-bug-author` copy — not written inline by
the coordinator, and not by another type's author.
