---
type: file_exists
path: .acs/state-machine/example-shop/runs/*/steps/create-pr/state.json
exists: true
---

The cursor reached the pipeline's last step and create-pr finished through
its post-hook (which writes this file) -- on this host, as a failure on gh.
A ship that stopped early has none.
