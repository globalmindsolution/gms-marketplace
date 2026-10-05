---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/audit-the-design-against-the-code-9784/steps/audit-design/iter-1/gaps.md }
pattern: '## Unimplemented\n(?:(?!\n## )[\s\S])*notifier'
flags: i
---

The notifier container (and its POST /notifications edge) is designed and no
longer built: hld/c4-container.md and hld/integration-map.md name it, and the
latest commit deleted src/notifier. It belongs under `## Unimplemented`, not
drifted or undocumented.
