---
type: file_exists
path: .git/acs/state-machine/example-shop/runs/*/requirements-refined.json
---

The feature (and the confirmed needs_design) is recorded through
`acs.py requirements refine`, the CLI that writes the run's refined
requirements -- `acs.py analysis publish` refuses a run with no feature
recorded. A run that published by hand never recorded one.
