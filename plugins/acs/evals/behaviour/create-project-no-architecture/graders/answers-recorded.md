---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/clarifications.json }
pattern: '"skill"\s*:\s*"create-project"[^}]*Python'
flags: i
---

The No-architecture fallback's step 2: every relayed answer is recorded
with `clarify.py add --skill create-project` before acting on it, so the
stack stands in the ledger in place of tech-stack.md. A run that stopped, or
scaffolded straight from the prompt, has no such entry.
