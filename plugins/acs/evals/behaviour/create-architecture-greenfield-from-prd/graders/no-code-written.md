---
type: regex
target: files
pattern: '^(?!docs/|\.acs/|\.claude/|\.eval-origin\.git/)[^\n]*\.(?:py|js|ts|toml|json|ya?ml|cfg)$|^(?:Dockerfile|docker-compose[^\n]*)$'
flags: m
match: not_contains
---

The architect writes the doc set only ("no other repo files are touched").
Source, build config or a compose file outside docs/ means the run started
scaffolding -- a scaffold ticket's job once this PR merges.
