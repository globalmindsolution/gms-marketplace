---
type: regex
target: { source: file, path: .gitignore }
pattern: '^\.acs/\n\*\.pyc\n\.claude/worktrees/\n$'
---

The broad rule is the user's configuration to decide: setup relays the
warning and never fixes it for them -- no `!.acs/` negation, no narrowed
rule. The one appended line is setup's own `.claude/worktrees/` entry, which
`.acs/` does not cover (Claude Code's worktrees live inside the checkout).
