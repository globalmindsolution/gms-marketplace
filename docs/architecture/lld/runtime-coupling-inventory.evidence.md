# Evidence sidecar — runtime-coupling-inventory.md

Companion `.evidence.md` file for
`docs/architecture/lld/runtime-coupling-inventory.md` (Decision B / ADR
0064). Relocated code-evidence citations, keyed by the body's existing
row/section identity (reused stable anchor, per C-1) -> `[path:line, ...]`.
The human body carries the bare source-file names only; this file is the
machine-facing citation record. Coverage is relocated, never reduced: both
pre-migration occurrence contexts (the surfaces table's "Verified entry
points" column and the anchor-verification table's "Anchor" column) are
preserved below as distinct entries — 22 total, never deduped to the 11
distinct anchors (MAR-528 added Surface #6's three).

## Runtime-coupled surfaces — "Verified entry points" column

- Surface #1 — Hook gating — Verified entry points: `hooks.json:3-14`
- Surface #1 — Hook gating — Verified entry points: `dispatch.py:40-53`
- Surface #1 — Hook gating — Verified entry points: `dispatch.py:145-167`
- Surface #1 — Hook gating — Verified entry points: `acs_lib/_common.py:31`
- Surface #2 — Session termination — Verified entry points: `hooks.json:64-74`
- Surface #2 — Session termination — Verified entry points: `dispatch.py:153-158`
- Surface #2 — Session termination — Verified entry points: `acs_lib/gates.py:539`
- Surface #4 — Per-role model/effort — Verified entry points: `acs_lib/settings.py:284-299`
- Surface #6 — Subagent & stop lifecycle — Verified entry points: `hooks.json:16-63`
- Surface #6 — Subagent & stop lifecycle — Verified entry points: `dispatch.py:119-142`
- Surface #6 — Subagent & stop lifecycle — Verified entry points: `acs_lib/lifecycle.py:397-584`

## Entry-point anchor verification record

- Entry-point anchor verification record — PreToolUse matcher `Skill`, command `dispatch.py pre`, timeout 30: `hooks.json:3-14`
- Entry-point anchor verification record — SessionEnd hook, command `dispatch.py session-end`, timeout 30: `hooks.json:64-74`
- Entry-point anchor verification record — `def skill_name_from_payload(payload)`: `dispatch.py:40-53`
- Entry-point anchor verification record — `def main()` — routes by skill, exit 2 on missing/blocked: `dispatch.py:145-167`
- Entry-point anchor verification record — session-end branch → `acs_lib.session_end`: `dispatch.py:153-158`
- Entry-point anchor verification record — `HOOKED_SKILLS` allowlist: `acs_lib/_common.py:31`
- Entry-point anchor verification record — `def resolve_role_model(settings, skill, role)`: `acs_lib/settings.py:284-299`
- Entry-point anchor verification record — `def session_end(payload)`: `acs_lib/gates.py:539`
- Entry-point anchor verification record — SubagentStart/SubagentStop (matcher `^acs:`), Stop and PreCompact registrations: `hooks.json:16-63`
- Entry-point anchor verification record — `LIFECYCLE_MODES` + `def run_lifecycle(mode, payload)` (fails OPEN): `dispatch.py:119-142`
- Entry-point anchor verification record — `subagent_start` / `subagent_stop` / `stop` / `pre_compact`: `acs_lib/lifecycle.py:397-584`

## Runtime-coupled surfaces — Surface #5 (Cost/token sourcing, MAR-1)

- Surface #5 — Cost/token sourcing — shipped `cost_basis` enum
  (`measured|apportioned|unavailable`): `skill-state.schema.json:45-47`

## Runtime-agnostic surfaces — `statusline.py` split note (MAR-1)

- Runtime-agnostic surfaces — `statusline.py` cost-sampling half —
  module docstring naming the Claude-Code-piped stdin payload: `statusline.py:16`
- Runtime-agnostic surfaces — `statusline.py` cost-sampling half —
  `main()` reads stdin then calls `cost_sampler.record_cost_sample(payload)`: `statusline.py:131-138`
