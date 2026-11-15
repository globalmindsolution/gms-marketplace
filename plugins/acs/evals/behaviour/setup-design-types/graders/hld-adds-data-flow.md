---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"hld_types"\s*:\s*\[[^\]]*"c4-context"[^\]]*"project-structure"[^\]]*"data-flow"'
---

The HLD choice is the defaults kept plus the one opt-in asked for, in catalog
order (setup normalises it).
