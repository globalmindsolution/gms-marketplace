#!/usr/bin/env bash
# A GREENFIELD product repo with a PRD and an architecture DIRECTORY that holds
# a C4 context view and a flows page but NO hld/tech-stack.md -- which
# create-project's Start does not count as an architecture doc set ("a
# directory without hld/tech-stack.md does not count"). So /acs:project finds
# no evidence (bootstrap) and create-project takes its No-architecture
# fallback: never a stop; the stack, layout and coverage tooling are
# confirmed with the user -- here, relayed in the prompt -- and each answer is
# recorded with `clarify.py add --skill create-project` BEFORE the scaffolder
# builds anything.
#
# acs_repo would plant src/, tests/ and a pyproject.toml, so the repo is
# initialised here instead -- same remote, identity, ticket prefix and
# reconciled counters seam as ../_fixtures/repo.sh's acs_repo.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

git init -q -b main
git remote add origin https://github.com/example/shop.git
git config user.email eval@example.com
git config user.name eval
mkdir -p .acs "$ACS_PARTITION"
printf '{\n  "ticket_prefix": "EVAL"\n}\n' > .acs/settings.json
printf '.acs/state-machine/\n.acs/settings.local.json\n.eval-origin.git/\n' > .gitignore
printf '# shop\n\nA small storefront service. Nothing is built yet: see docs/.\n' > README.md
printf '{"next": 1, "reconciled": true, "seed_source": "explicit-user", "seeded_at": "%s"}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$ACS_PARTITION/counters.json"
git add -A
git commit -qm "Empty product repo"

acs_prd
acs_architecture
acs_local_origin
