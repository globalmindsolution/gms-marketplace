---
type: regex
target: { source: file, path: .github/workflows/ci.yml }
pattern: '^name: ci\n[\s\S]*python3 -m coverage run -m pytest tests && python3 -m coverage report\n$'
---

The existing workflow is not rewritten (an in-place edit is not a created
path, so the files grader cannot see it; this one can).
