---
type: tool_used
tool: Bash
input_match: '(?:--version[\s=]+[''"]?v?2\.5\.0\b)|(?:release/v?2\.5\.0)|(?:"version"\s*:\s*\\"2\.5\.0)'
min: 0
max: 0
---

"Do not guess a version": no helper call with `--version 2.5.0`, no
`release/v2.5.0` branch, no manifest written at 2.5.0. Padding "2.5" to 2.5.0
is exactly the guess the skill forbids -- the user may have meant 2.5.1.
