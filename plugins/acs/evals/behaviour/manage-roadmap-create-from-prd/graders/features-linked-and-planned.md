---
type: regex
target: { source: file, path: docs/product/roadmap.md }
pattern: '^(?=[\s\S]*\]\((?:\./)?features/customer-listing/prd\.md\))(?=[\s\S]*\]\((?:\./)?features/card-checkout/prd\.md\))(?=[\s\S]*\]\((?:\./)?features/order-tracking/prd\.md\))(?![\s\S]*Status:\s*(?:delivered|in progress))(?=[\s\S]*- Status: planned)'
---

Each milestone links the feature PRD it delivers, and every status is the
derived one: no tickets exist, so every milestone is `planned` -- a run that
asserted `delivered` for the shipped customer listing wrote a status the
tickets do not bear out.
