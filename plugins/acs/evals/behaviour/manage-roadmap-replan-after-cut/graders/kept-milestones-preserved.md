---
type: regex
target: { source: file, path: docs/product/roadmap.md }
pattern: '### Storefront — v2\.4\.0\n\n- Status: planned\n- Features: \[Customer listing\]\(features/customer-listing/prd\.md\)\n- Epics: none yet\n\nThe product listing every merchant starts from\.\n\n### Checkout — v2\.5\.0\n\n- Status: planned\n- Features: \[Card checkout\]\(features/card-checkout/prd\.md\)\n- Epics: none yet\n\nShoppers pay by card through the external gateway\.\n[\s\S]*\| v2\.4\.0 \| Storefront \| — \| planned \|\n\| v2\.5\.0 \| Checkout \| — \| planned \|\n'
---

Replan edits in place: the milestones the change does not touch, and their
rows, are byte-for-byte what they were. A regenerated roadmap that reworded
them fails here.
