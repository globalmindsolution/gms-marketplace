#!/usr/bin/env bash
# A shipped Python product with a PRD (99.9% availability, p95 300 ms) and an
# architecture set create-docs recognises (it carries hld/tech-stack.md and a
# deployment view), no product doc sets yet, and a local bare repository
# standing in for GitHub so the operations set's delivery branch can be pushed.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo
acs_prd
acs_architecture
cat > docs/architecture/hld/tech-stack.md <<'MD'
# Tech stack

## Languages

- Python 3.12 (package `shop`, src layout).

## Frameworks

- pytest for unit tests, with pytest-cov for coverage.

## Conventions

- Tests live in `tests/`, one `test_*.py` per module.
MD
cat > docs/architecture/hld/deployment.md <<'MD'
# Deployment

```mermaid
flowchart LR
  lb[load balancer] --> shop[shop container]
```

One `shop` container behind a load balancer. Logs go to stdout as JSON.
MD
git add -A && git commit -qm "Tech stack and deployment"
acs_local_origin
