---
type: regex
target: { source: file, path: pyproject.toml }
pattern: 'fail[_-]under\s*=\s*"?90\b'
---

The coverage tooling fails the run below the 90% target -- `fail_under = 90`
under `[tool.coverage.report]` or `--cov-fail-under=90` in pytest's addopts.
A coverage config that never fails enforces nothing.
