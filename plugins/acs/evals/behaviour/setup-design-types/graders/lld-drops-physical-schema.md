---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"lld_types"\s*:\s*\[[^\]]*"api-contract"[^\]]*"logical-erd"[^\]]*"state"'
---

The LLD choice keeps the defaults the user did not drop.
