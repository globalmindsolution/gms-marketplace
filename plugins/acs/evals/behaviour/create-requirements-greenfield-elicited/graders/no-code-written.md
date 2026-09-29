---
type: regex
target: files
pattern: '^(?!docs/|\.acs/|\.claude/|\.eval-origin\.git/)[^\n]*\.(?:py|js|ts|toml|json|ya?ml|cfg)$'
flags: m
match: not_contains
---

A requirements run is docs-only: the authors write area files and nothing
else. Greenfield has no code to cite and none to write.
