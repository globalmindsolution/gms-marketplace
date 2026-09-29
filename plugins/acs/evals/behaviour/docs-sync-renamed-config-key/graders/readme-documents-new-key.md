---
type: regex
target: { source: file, path: README.md }
pattern: '(?<![\s\S])(?![\s\S]*^- `SHOP_PAGE_SIZE`)[\s\S]*^- `SHOP_CUSTOMERS_PAGE_SIZE`'
flags: m
---

README.md's Configuration list names `SHOP_CUSTOMERS_PAGE_SIZE` as the
setting, and no list item still offers `SHOP_PAGE_SIZE` as one. A migration
note that mentions the old name in prose ("renamed from ...") is fine; a
setting line that still names it is the stale doc.
