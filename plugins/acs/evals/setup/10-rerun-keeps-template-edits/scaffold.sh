#!/usr/bin/env bash
# The shared python repo (../_fixtures/python-repo.sh), set up before with the
# document templates scaffolded (ADR-0148) -- through the plugin's own writer --
# after which the team edited its feature PRD template: a Rollout section.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/python-repo.sh"

plugin="$(cd "$here/../../.." && pwd)"
python3 "$plugin/hooks/scripts/acs.py" setup apply --answers - >/dev/null <<'JSON'
{"settings": {"ticket_prefix": "PAY"}, "templates": true}
JSON
python3 - <<'PY'
path = ".acs/templates/prd-feature-default.md"
text = open(path, encoding="utf-8").read()
open(path, "w", encoding="utf-8").write(text.replace(
    "## Out of scope", "## Rollout\n\n<!-- Beta group, feature flag, full launch. -->\n\n## Out of scope"))
PY
git add -A
git commit -qm "Configure acs; our feature PRD template adds Rollout"
