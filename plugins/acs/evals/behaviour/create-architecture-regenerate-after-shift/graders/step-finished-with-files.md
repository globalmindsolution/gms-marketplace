---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/regenerate-the-architecture-after-the-shift-1304/steps/create-architecture/state.json }
pattern: '^(?=[\s\S]*"status"\s*:\s*"completed")(?=[\s\S]*"files"\s*:\s*\[[^\]]*"docs/architecture/hld/c4\-container\.md")(?=[\s\S]*"files"\s*:\s*\[[^\]]*"docs/architecture/hld/integration\-map\.md")'
---

The mandatory Finish ran through the post-hook, which records the invocation
`completed` and persists the result's states. The documents stay local -- no
branch, no commit, no PR (ADR-0127) -- so `states.files` must list every HLD file it wrote (two pinned here),
repo-relative: it is exactly what `/acs:create-pr` groups and commits
later. A file written but not recorded is a change nobody was told about.
