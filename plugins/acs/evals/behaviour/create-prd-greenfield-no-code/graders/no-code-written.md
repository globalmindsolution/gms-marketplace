---
type: regex
target: files
pattern: '^(?!docs/|\.acs/|\.claude/|\.eval-origin\.git/)[^\n]*\.(?:py|js|ts|toml|json|ya?ml|cfg)$'
flags: m
match: not_contains
---

A PRD run is docs-only: the author mutates only `<prd>` and `<roadmap>`. A
source, build or config file created outside docs/ (and acs's own state)
means the run started building the product -- a scaffold ticket's job,
after /acs:create-architecture.
