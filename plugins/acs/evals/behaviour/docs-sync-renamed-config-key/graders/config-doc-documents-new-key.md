---
type: regex
target: { source: file, path: docs/configuration.md }
pattern: '(?<![\s\S])(?![\s\S]*^\|\s*`SHOP_PAGE_SIZE`)[\s\S]*^\|\s*`SHOP_CUSTOMERS_PAGE_SIZE`\s*\|'
flags: m
---

The second place the key is documented: docs/configuration.md's table row
names `SHOP_CUSTOMERS_PAGE_SIZE`, and no row still names `SHOP_PAGE_SIZE`.
Fixing the README alone -- the first hit a grep finds -- fails here.
