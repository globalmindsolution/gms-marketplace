---
type: regex
target: { source: file, path: docs/product/prd.md }
pattern: '^(?=[\s\S]*^##\s+Vision\s*\n[\s\S]*^##\s+Problem statement\s*\n[\s\S]*^##\s+Target users & personas\s*\n[\s\S]*^##\s+Goals & success metrics\s*\n[\s\S]*^##\s+Features \(prioritized\)\s*\n[\s\S]*^##\s+Non-functional requirements\s*\n[\s\S]*^##\s+Constraints & assumptions\s*\n[\s\S]*^##\s+Out of scope\s*$)(?![\s\S]*^##\s+Rollout)'
flags: mi
---

The repo replaces only the feature template, so the hub keeps the built-in
hub template's eight sections, in order -- and no Rollout section of its own.
