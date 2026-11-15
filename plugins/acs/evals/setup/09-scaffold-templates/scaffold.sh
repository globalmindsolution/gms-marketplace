#!/usr/bin/env bash
# The shared python repo (../_fixtures/python-repo.sh), never set up: no
# .acs/templates/ yet.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/python-repo.sh"
