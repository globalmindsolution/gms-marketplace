---
type: file_exists
path: .acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements/local/analysis.md
---

With `docs.share_run_documents: false` saved, `docs where` (and `artifacts
show`'s `paths["analysis.md"]`) resolve the analysis to the run's own state
folder, `steps/analyze-requirements/local/analysis.md` (ADR-0132): later steps
still read it there, and it never enters the repo.
