---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/review-code/handoff-context.md }
pattern: 'negative[\s\S]*(?:out of scope|(?:separate|own|new|follow-up|later) ticket)|(?:out of scope|(?:separate|own|new|follow-up|later) ticket)[\s\S]*negative'
flags: i
---

Step 3's flush lands at `steps/<in-flight step>/handoff-context.md` -- here
`steps/review-code/` -- and carries the decision nothing on disk records:
negative limits are out of scope, their own ticket. `handoff.py` writes its own
derived file at the RUN root, never here, so this can only be the skill's
flush.
