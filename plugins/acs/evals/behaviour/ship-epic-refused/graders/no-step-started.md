---
type: file_exists
path: .acs/state-machine/example-shop/runs/*/steps/**
exists: false
---

The epic brake refuses the Skill call itself, before any step is started, so
no step state exists. One here means a step ran on the epic after all --
started by hand past the refusal (`acs step start` does not re-apply the
brake), or /acs:create-tech-design run by ship, which only points at it.
