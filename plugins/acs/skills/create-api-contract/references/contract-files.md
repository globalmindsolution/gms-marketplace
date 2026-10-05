# Machine-readable contract files — resolving `contracts_mode`

Read this once per run, before the first subagent is spawned: it resolves the
`contracts_mode` every task's `<constraints>` carries.

The repo's machine-readable contracts — an OpenAPI document, JSON Schemas,
`.proto` files, a GraphQL SDL, a CLI reference generated from the parser,
whatever this repo already uses — live where the repo keeps them, else at
`docs/api/`, the conventional default. Locate them the way any session finds a
document: CLAUDE.md and whatever docs index it or the repo points at (e.g.
`docs/README.md`), then a Glob/Grep by file name or content, and `docs/api/`.
Resolve the mode ONCE, before the first subagent is spawned, and state it in
every task's `<constraints>`:

- none found → mode `no-machine-readable-contracts`. Do NOT invent the
  convention: record that in `## Contract files` and leave the tree absent.
  Introducing a contract format a repo has never used is an architecture
  decision, not this skill's call — raise it as a question if it matters; a
  format the user adopts goes in `docs/api/`.
- found → mode is the repo-relative directory that holds them
  (`<contracts_dir>`). Identify the files that describe the touched surface (by
  reading them, not by guessing filenames) and update them as part of this run,
  in the format they already use.

Those two token values are what `<constraint name="contracts_mode">` carries
into every phase, so the contract-author and the contract-reviewer work against
the same resolution. The same resolution decides whether the contract-authors
run sliced (see Writer slices): decide that here too, once, before the first
spawn.
