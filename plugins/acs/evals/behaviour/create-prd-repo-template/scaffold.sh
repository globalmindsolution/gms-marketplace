#!/usr/bin/env bash
# A greenfield product whose team keeps its own feature PRD template
# (ADR-0147): `.acs/templates/prd-feature-default.md` adds a `## Rollout`
# section between Dependencies and Out of scope. No PRD yet. A local bare
# repository stands in for GitHub.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo
git rm -rq src tests pyproject.toml CHANGELOG.md
cat > README.md <<'MD'
# groomr

Online booking for independent dog groomers. Nothing is built yet.
MD
mkdir -p .acs/templates
cat > .acs/templates/prd-feature-default.md <<'MD'
<!-- Our team's feature PRD template: the built-in's six sections plus Rollout. -->
# <Feature name>

## Summary

## Goals served

## Requirements

<!-- - **R1** — <requirement> -->

## Acceptance criteria

## Dependencies

## Rollout

<!-- Who gets it first and how it is switched on: beta group, feature flag, full launch. -->

## Out of scope
MD
git add -A && git commit -qm "Start groomr with our PRD template"
acs_local_origin
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
# The run the skill resumes: a ticketless run (ADR-0127), opened here so
# its id -- and so every grader path -- is deterministic.
acs run new --prompt "Define the groomr product with our templates" > /dev/null
