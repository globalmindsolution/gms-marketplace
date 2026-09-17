# Evidence sidecar — contracts.md

Companion `.evidence.md` file for `docs/architecture/lld/contracts.md`.
Relocated code-evidence citation, keyed by the body's existing heading
identity (stable anchor, per the sidecar convention `create-requirements-
executor.md` follows, reused here rather than forked) -> `[path:line]`.

- Ticket classification fields (MAR-56) — `needs_design` no longer affects
  the delivery path as of ADR-0095: judged once from `plan.md` and recorded on
  `pipeline-state.json`; `derive_lane` and the module that held it are both retired
  (what is left of it is `src/acs/hooks/scripts/acs_lib/planrules.py`)
