#!/usr/bin/env bash
# /acs:set-doc-status retiring a cut feature's documents with a reason
# (ADR-0130). Leadership cut gift cards; every gift-cards document is
# approved, and the wishlist feature's documents -- approved too -- stay. All
# blocks are written through `acs.py design`, never by hand:
#
#   docs/product/prd.md, roadmap.md                         approved v1
#   docs/product/features/gift-cards/analysis.md            approved v1  <- deprecate
#   docs/architecture/hld/tech-stack.md                     implemented v1
#   docs/architecture/lld/gift-cards/api/gift-cards-api.md  approved v1  <- deprecate
#   docs/architecture/lld/gift-cards/data/ledger.md         approved v1  <- deprecate
#   docs/architecture/lld/wishlist/api/wishlist-api.md      approved v1  (untouched)
#
# A local bare repository stands in for GitHub.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }

acs_repo
acs_prd

P=docs/product/features
A=docs/architecture
mkdir -p $P/gift-cards $A/hld $A/lld/gift-cards/api $A/lld/gift-cards/data $A/lld/wishlist/api
printf '# Gift cards — analysis\n\nShoppers buy and redeem gift cards at checkout.\n' \
  > $P/gift-cards/analysis.md
printf '# Tech stack\n\nPython 3, pytest; one package per container under src/.\n' > $A/hld/tech-stack.md
printf '# Gift cards API\n\n## POST /gift-cards\n\nBody: `{amount}`. Response 201: `{code}`.\n' \
  > $A/lld/gift-cards/api/gift-cards-api.md
printf '# Gift card ledger\n\n```mermaid\nerDiagram\n  GIFT_CARD ||--o{ LEDGER_ENTRY : records\n```\n' \
  > $A/lld/gift-cards/data/ledger.md
printf '# Wishlist API\n\n## POST /wishlist/items\n\nBody: `{product_id}`. Response 201.\n' \
  > $A/lld/wishlist/api/wishlist-api.md

acs design init --status approved docs/product/prd.md docs/product/roadmap.md > /dev/null
acs design init --status approved --feature gift-cards $P/gift-cards/analysis.md \
  $A/lld/gift-cards/api/gift-cards-api.md $A/lld/gift-cards/data/ledger.md > /dev/null
acs design init --status implemented $A/hld/tech-stack.md > /dev/null
acs design init --status approved --feature wishlist $A/lld/wishlist/api/wishlist-api.md > /dev/null
git add -A && git commit -qm "Gift cards and wishlist documents"
acs_local_origin
