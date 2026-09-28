---
type: regex
target: { source: file, path: .github/workflows/acs-e2e.yml }
pattern: '^# team e2e workflow: boots the service on :8080, then runs e2e/ against it\n[\s\S]*python3 -m http\.server 8080 & python3 -m pytest -q e2e\n$'
---

The team's workflow is still there, first line to last. Copying acs's
`acs-e2e.yml` template over it -- the scaffold-able branch this repo does not
qualify for -- replaces both lines.
