# The integration pass — synthesis, not just a join

Read when more than one doc area changed docs, or any area recorded an
out-of-area item. After every area has returned and BEFORE the drift-reviewer,
spawn ONE more `acs:docs-sync-doc-updater` with `slice="integration"` — the
pattern `/acs:code-complex`'s final integration implementer already uses. Its task names every area's
`iter-<n>/authoring-<area>.md` and `iter-<n>/doc-updater-<area>.json`. It
runs alone, after the areas, so its edits cannot race theirs. It reconciles
ONLY the seams:

- **docs index pages** — `docs/README.md` or whatever docs index the repo
  keeps, the requirements set's README/index, the architecture set's
  overview: every doc an area added, renamed or removed is listed (or
  delisted) there;
- **cross-links between areas** — an ADR ↔ the HLD section it changes, a
  requirement ↔ the architecture flow that realizes it, a README/API doc ↔
  the requirement or ADR it cites: every link resolves and both ends say the
  same thing; shared terms and IDs are spelled the same across areas;
- **each area's "Out-of-area impact" notes** — every out-of-area item must
  be applied by the owning area or explicitly resolved. The integration pass
  records each item's disposition: *applied by `<area>`* (citing that area's
  file), *applied here* (only when the item is itself a seam),
  or *not needed* (with the evidence). An item that is substance its owning
  area missed is not the integration pass's to write: it lists it as
  *unapplied → `<area>`*, you re-run that area's doc-updater once for the
  same iteration with the item in `<context>`, then re-run the integration
  pass; still unapplied, it goes to the drift-reviewer as-is.

It never rewrites an area's substance. Where two areas' notes contradict each
other, it records the resolution and its evidence under a `## Synthesis`
section of its notes, or returns `status="needs_input"` with a question —
never silently picks one. It writes only the seam files, lists them in
its report like the areas, commits nothing, and writes
`iter-<n>/authoring-integration.md` and `iter-<n>/doc-updater-integration.json`
listing each seam it changed (file, what, why, which areas). **Skipped when
only one area had changes** (at most one area's report lists a changed
doc, and no area recorded an out-of-area item): with a single writer there is
no seam.
