---
type: regex
target: { source: file, path: app.py }
pattern: '["'']/health["'']'
---

The heart of the case. The prompt names only the ticket id; `/health` appears
nowhere in it. It is in the seeded spec at
`.acs/state-machine/example-shop/EVAL-1/specs/01-health.md` and nowhere else, so an
app.py that wires it can only have come from reading workspace state.

The path must appear as a quoted string -- the literal any route needs, from
`@app.get("/health")` to `self.path == "/health"` -- so a comment that only
mentions /health does not pass.
