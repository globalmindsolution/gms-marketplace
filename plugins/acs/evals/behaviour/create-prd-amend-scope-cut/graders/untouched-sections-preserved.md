---
type: regex
target: { source: file, path: docs/product/prd.md }
pattern: '^(?=[\s\S]*## Vision\n\nLet small merchants sell online without running any infrastructure\.\n\n## Problem statement\n\nMerchants lose sales because setting up a storefront with payments takes weeks\nof engineering they cannot afford\.\n\n## Target users & personas\n\n- \*\*Merchant\*\* — lists products, fulfils orders\.\n- \*\*Shopper\*\* — browses and pays\.\n\n## Goals & success metrics\n\n\| Goal \| Metric \|\n\|-{3}\|-{3}\|\n\| G1 Checkout that converts \| checkout conversion >= 3\.5% of shopper sessions by 2027-06-30 \|\n\| G2 Reliable service \| 99\.9% monthly availability, every calendar month from 2027-01 \|\n)(?=[\s\S]*## Non-functional requirements\n\n- p95 API latency under 300 ms\.\n- Unit test coverage at least 90%\.\n\n## Constraints & assumptions\n\n- One Python 3\.12 service; card payments only through an external gateway\.\n)'
---

Amend mode edits in place and preserves untouched sections exactly: Vision,
Problem statement, personas and Goals (one contiguous block) and the NFR and
Constraints sections are byte-for-byte what the scaffold committed. A run
that regenerated the PRD rewords at least one of them.
