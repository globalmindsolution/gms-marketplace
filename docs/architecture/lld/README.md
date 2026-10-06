# LLD — Feature index

The low-level design, one folder per PRD feature. Each feature folder holds its
living documents — `api/` (one file per interface) and `flows/` (sequence and
state diagrams) — plus one folder per change that recorded a design for it,
named by the change's ticket id. The living documents carry version front
matter (`acs.py design list --feature <feature>` shows their status); the
per-change records and these READMEs do not.

| Feature | Folder | HLD containers it covers |
|---------|--------|--------------------------|
| acs | [`acs/`](acs/README.md) | acs Skills, acs Subagents, acs Hook & helper layer, acs Schemas & templates, Workspace store ([c4-container.md](../hld/c4-container.md)) |

The system-level views are in [`../hld/`](../hld/overview.md).
