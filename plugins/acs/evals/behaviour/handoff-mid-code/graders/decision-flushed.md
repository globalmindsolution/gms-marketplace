---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/code/handoff-context.md }
pattern: 'clamp[\s\S]*\b400\b|\b400\b[\s\S]*clamp'
flags: i
---

Step 3's soft-context flush, at `steps/<in-flight step>/handoff-context.md`,
carries the decision the prompt gave and nothing on disk records: clamp to
100, do not reject with a 400. `handoff.py` writes its own derived file at the
RUN root, never here, so this file can only have come from the skill's flush.
