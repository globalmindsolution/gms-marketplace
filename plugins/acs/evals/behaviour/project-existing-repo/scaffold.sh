#!/usr/bin/env bash
# An EXISTING Python product (src/, tests/, pyproject.toml) with a PRD and no
# CI, pre-commit or coverage config. /acs:project's declared evidence table
# finds pyproject.toml, so the mode is `standardize` and the leg is
# standardize-project -- never create-project, whose greenfield gate would
# refuse this repo. The bare local origin lets the leg push its branch.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_local_origin
