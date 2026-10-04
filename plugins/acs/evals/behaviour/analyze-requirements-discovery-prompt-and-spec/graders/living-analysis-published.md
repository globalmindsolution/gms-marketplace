---
type: file_exists
path: docs/product/features/order-tracking/analysis.md
---

A standalone run with no ticket is a Discovery run (ADR-0129): its analysis is
the feature's living analysis, published at
`<prd_dir>/features/<feature>/analysis.md` -- here the PRD's F3 Order
tracking, slug `order-tracking` (`acs.py slug --text "Order tracking"`). A
draft left in the workspace, an analysis filed under another slug, or one
written to a development or ticket folder fails.
