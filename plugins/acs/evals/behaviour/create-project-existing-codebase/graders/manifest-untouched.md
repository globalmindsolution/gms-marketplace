---
type: regex
target: { source: file, path: pyproject.toml }
pattern: '\[tool\.(coverage|ruff|pytest\.ini_options\][^\[]*addopts)'
match: not_contains
---

The existing build manifest is not rewritten into a scaffold's: no coverage,
ruff or pytest-addopts config is added to it.
