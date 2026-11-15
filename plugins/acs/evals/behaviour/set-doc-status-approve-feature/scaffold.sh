#!/usr/bin/env bash
# /acs:set-doc-status approving one feature's documents (ADR-0130). The repo
# carries an approved PRD and roadmap, two features' living analyses and two
# features' LLD documents, every block written through `acs.py design` --
# never by hand:
#
#   docs/product/prd.md, roadmap.md                       approved v1
#   docs/product/features/wishlist/analysis.md            proposed v2  <- approve
#   docs/product/features/checkout/analysis.md            proposed v1  (untouched)
#   docs/architecture/hld/tech-stack.md                   implemented v1
#   docs/architecture/lld/wishlist/api/wishlist-api.md    proposed v1  <- approve
#   docs/architecture/lld/wishlist/flows/add-item.md      proposed v1  <- approve
#   docs/architecture/lld/checkout/api/checkout-api.md    proposed v1  (untouched)
#
# The analysis is at v2 so a run that bumps instead of approving shows. A
# local bare repository stands in for GitHub.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }

acs_repo
acs_prd
acs design init --status approved docs/product/prd.md docs/product/roadmap.md > /dev/null

P=docs/product/features
A=docs/architecture
mkdir -p $P/wishlist $P/checkout $A/hld $A/lld/wishlist/api $A/lld/wishlist/flows $A/lld/checkout/api
printf '# Wishlist — analysis\n\nShoppers save products to a wishlist and move them to the cart.\n' \
  > $P/wishlist/analysis.md
printf '# Checkout — analysis\n\nCard checkout through the external payments gateway.\n' \
  > $P/checkout/analysis.md
printf '# Tech stack\n\nPython 3, pytest; one package per container under src/.\n' > $A/hld/tech-stack.md
printf '# Wishlist API\n\n## POST /wishlist/items\n\nBody: `{product_id}`. Response 201.\n' \
  > $A/lld/wishlist/api/wishlist-api.md
printf '# Add to wishlist\n\n```mermaid\nsequenceDiagram\n  Shopper->>shop: POST /wishlist/items\n  shop-->>Shopper: 201\n```\n' \
  > $A/lld/wishlist/flows/add-item.md
printf '# Checkout API\n\n## POST /checkout\n\nBody: `{cart_id, card_token}`. Response 201.\n' \
  > $A/lld/checkout/api/checkout-api.md

acs design init --status proposed --feature wishlist $P/wishlist/analysis.md > /dev/null
acs design bump $P/wishlist/analysis.md > /dev/null
acs design init --status proposed --feature checkout $P/checkout/analysis.md > /dev/null
acs design init --status implemented $A/hld/tech-stack.md > /dev/null
acs design init --status proposed --feature wishlist \
  $A/lld/wishlist/api/wishlist-api.md $A/lld/wishlist/flows/add-item.md > /dev/null
acs design init --status proposed --feature checkout $A/lld/checkout/api/checkout-api.md > /dev/null
git add -A && git commit -qm "Wishlist and checkout documents"
acs_local_origin
