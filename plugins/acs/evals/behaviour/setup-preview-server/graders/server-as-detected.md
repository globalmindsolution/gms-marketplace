---
type: regex
target: { source: file, path: .claude/launch.json }
pattern: '"runtimeExecutable"\s*:\s*"pnpm"[\s\S]*"runtimeArgs"\s*:\s*\[\s*"run"\s*,\s*"dev"\s*\][\s\S]*"port"\s*:\s*5173'
---

The detected candidate (pnpm lockfile, vite dev script, vite's default port),
written as shown to the user, not a different guess.
