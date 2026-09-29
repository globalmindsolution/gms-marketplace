---
type: regex
target: { source: file, path: docs/quality/coverage-policy.md }
pattern: '^(?=[\s\S]*^#{1,3}\s+Target and hard-fail rule)(?=[\s\S]*^#{1,3}\s+Measurement per stack)(?=[\s\S]*\b90\s?%)(?=[\s\S]*pytest)'
flags: mi
---

The file the interrupted run never started, written on resume from its
template and tailored: the PRD's 90% target measured with pytest.
