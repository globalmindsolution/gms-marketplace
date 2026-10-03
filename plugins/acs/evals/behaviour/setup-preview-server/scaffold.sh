#!/usr/bin/env bash
# The shared Python repo with a Vite front end added: a package.json whose
# `dev` script runs vite and a pnpm lockfile, committed, and no
# .claude/launch.json. SKILL.md Step 2 offers the Desktop app's preview-server
# config only "when launch.exists is false and there are candidates"; the
# detector guesses `pnpm run dev` on vite's default port 5173. Asked for that
# alone, setup shows the guess and writes it through `setup apply`.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
cat > package.json <<'JSON'
{
  "name": "shop-web",
  "private": true,
  "scripts": { "dev": "vite", "build": "vite build" }
}
JSON
: > pnpm-lock.yaml
git add -A && git commit -qm "web front end"
