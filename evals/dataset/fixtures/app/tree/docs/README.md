# orders — documentation

- [architecture.md](architecture.md) — modules, data flow, the one state file.
- [api.md](api.md) — the HTTP API.
- [adr/](adr/) — decision records: JSON file storage, idempotent charges.

Every module under `orders/` is listed in `architecture.md`; a change that adds
or removes a module updates that table in the same change.
