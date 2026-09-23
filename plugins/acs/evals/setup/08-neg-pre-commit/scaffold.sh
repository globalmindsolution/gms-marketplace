#!/usr/bin/env bash
# The shared python repo (../_fixtures/python-repo.sh).
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/python-repo.sh"
