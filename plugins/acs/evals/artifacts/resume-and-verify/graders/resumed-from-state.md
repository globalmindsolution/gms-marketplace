---
type: regex
target: { source: file, path: app.py }
pattern: '/health'
---

The heart of the case. The prompt names only the ticket id; `/health` appears
nowhere in it. It is in the seeded spec at
`.acs-workspace/example-shop/EVAL-1/specs/01-health.md` and nowhere else, so an
app.py that wires it can only have come from reading workspace state.
