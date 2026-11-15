---
type: regex
target: { source: file, path: .acs/templates/templates.lock.json }
pattern: '"prd-default"\s*:\s*\{\s*"sha256"\s*:\s*"[0-9a-f]{64}"'
---

The lock records each copy's built-in hash, written by `acs.py setup apply`
(never by hand): it is what lets a later re-run refresh an untouched copy and
keep an edited one.
