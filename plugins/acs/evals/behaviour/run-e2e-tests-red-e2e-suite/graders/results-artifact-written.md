---
type: file_exists
path: .git/acs/state-machine/example-shop/test-runs/run-*/results.json
---

Step 3's auditable artifact, at the repo-level `test-runs/<run-id>/results.json`
the skill names -- not inside a ticket partition. Its `run-<ISO8601>` id is a
timestamp, so a grader can name only the pattern, not read the file: its
contents are graded through the regression ticket that links it and through
the reply.
