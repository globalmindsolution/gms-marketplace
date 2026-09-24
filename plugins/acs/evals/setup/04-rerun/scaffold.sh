#!/usr/bin/env bash
# The shared python repo (../_fixtures/python-repo.sh),
# plus a setup run from before.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/python-repo.sh"

plugin="$(cd "$here/../../.." && pwd)"
python3 "$plugin/hooks/scripts/acs.py" setup apply --answers - >/dev/null <<'JSON'
{"settings": {"formats": {"pr_title": "[{ticket_id}] {title}"}}, "ci": ["conventions"]}
JSON
git add -A
git commit -qm "Configure acs"
