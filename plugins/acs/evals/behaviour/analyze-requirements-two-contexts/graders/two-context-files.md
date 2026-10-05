---
type: regex
target: files
pattern: '^docs/development/checkout-with-card-payments/EVAL-1/analysis/[a-z0-9]+(?:-[a-z0-9]+)*\.md$[\s\S]*^docs/development/checkout-with-card-payments/EVAL-1/analysis/[a-z0-9]+(?:-[a-z0-9]+)*\.md$'
flags: m
---

The change spans two bounded contexts -- cancelling an order
(`src/shop/orders.py`) and refunding a card charge (`src/shop/payments.py`),
each with its own rules -- so the folder holds at least two context files
beside the README, each named in plain words, kebab-case. One file holding
both contexts, or one long `analysis.md`, fails.
