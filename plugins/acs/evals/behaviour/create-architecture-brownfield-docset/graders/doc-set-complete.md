---
type: regex
target: files
pattern: '^(?=[\s\S]*^docs/architecture/hld/overview\.md$)(?=[\s\S]*^docs/architecture/hld/c4-context\.md$)(?=[\s\S]*^docs/architecture/hld/c4-container\.md$)(?=[\s\S]*^docs/architecture/hld/c4-component\.md$)(?=[\s\S]*^docs/architecture/hld/data-model\.md$)(?=[\s\S]*^docs/architecture/hld/deployment\.md$)(?=[\s\S]*^docs/architecture/hld/tech-stack\.md$)(?=[\s\S]*^docs/architecture/hld/project-structure\.md$)(?=[\s\S]*^docs/architecture/lld/contracts\.md$)(?=[\s\S]*^docs/architecture/lld/flows/list-customers\.md$)(?=[\s\S]*^docs/architecture/lld/flows/health-check\.md$)'
flags: m
---

The Output contract, created by this run at the conventional default (no
`hld/tech-stack.md` existed, so `<architecture_dir>` is `docs/architecture/`):
all eight HLD files, `lld/contracts.md`, and one flow file per confirmed flow
under the names the request fixed.
