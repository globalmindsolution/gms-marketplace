#!/usr/bin/env bash
# create-ticket (remote import): the shop repo with its settings pointing the
# tracker at GitHub (provider github, owner example). The run has no network
# and no gh credentials -- whether gh is missing or unauthenticated, the
# `gh issue view 123` pull fails, and SKILL.md classifies that pull as
# CRITICAL: surface gh's stderr with the canonical hint, no fallback.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd  # tickets are made from the PRD (ADR-0144)
cat > .acs/settings.json <<'JSON'
{
  "ticket_prefix": "EVAL",
  "tracker": {
    "provider": "github",
    "github": { "owner": "example" }
  }
}
JSON
git add -A
git commit -qm "Track tickets in GitHub"
