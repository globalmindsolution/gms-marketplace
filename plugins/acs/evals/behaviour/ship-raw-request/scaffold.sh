#!/usr/bin/env bash
# No ticket at all: just the product repo, with a local origin standing in
# for GitHub. The request arrives as free text, which ship's Step 2 treats as
# a SUBJECT -- "a new run from that prompt" -- so ship.yaml's steps run over
# the prompt (or over a ticket minted from it, if the run takes that route;
# the graders accept either). The pipeline ends at create-pr, whose critical
# gh base detection fails before any push, and ship stops there.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_local_origin
