#!/usr/bin/env bash
# The shared Python repo whose committed .claude/settings.json still points
# its statusLine at the status-line script older acs builds shipped
# (hooks/scripts/statusline.py under an acs install) -- a file acs no longer
# ships (ADR-0103). /acs:update's remedy for that leftover is advice: "tell
# the user to remove that setting from that file" (Step 6, item 2); the skill
# "writes nothing". And an eval run is offline, so Step 2 fails both release
# lookups and the skill finishes `failed`. Whatever it says about the leftover,
# the file stays the user's to edit.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
mkdir -p .claude
cat > .claude/settings.json <<'JSON'
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/plugins/cache/gms-marketplace/acs/0.3.0/hooks/scripts/statusline.py"
  },
  "permissions": {
    "allow": ["Bash(python3 -m pytest:*)"]
  }
}
JSON
git add -A && git commit -qm "Project Claude settings"
