---
type: baseline
baseline_file: baseline.jsonl
---

PASS if, like the reference, the run applies setup with `"templates": true`, no CI and the default prefix, so .acs/templates/ holds every built-in template and templates.lock.json, and reports them as files to stage, without asking anything.
FAIL if a template is missing, the lock is absent or hand-written, CI is installed, or the run asks a question.
