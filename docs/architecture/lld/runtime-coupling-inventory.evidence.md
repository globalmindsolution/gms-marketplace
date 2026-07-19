# Evidence sidecar — runtime-coupling-inventory.md

Companion `.evidence.md` file for
`docs/architecture/lld/runtime-coupling-inventory.md` (Decision B / ADR
0064). Relocated code-evidence citations, keyed by the body's existing
row/section identity (reused stable anchor, per C-1) -> `[path:line, ...]`.
The human body carries the bare source-file names only; this file is the
machine-facing citation record. Coverage is relocated, never reduced: both
pre-migration occurrence contexts (the surfaces table's "Verified entry
points" column and the anchor-verification table's "Anchor" column) are
preserved below as distinct entries — 16 total, never deduped to the 8
distinct anchors.

## Runtime-coupled surfaces — "Verified entry points" column

- Surface #1 — Hook gating — Verified entry points: `hooks.json:3-14`
- Surface #1 — Hook gating — Verified entry points: `dispatch.py:25-38`
- Surface #1 — Hook gating — Verified entry points: `dispatch.py:41-75`
- Surface #1 — Hook gating — Verified entry points: `acs_lib.py:43`
- Surface #2 — Session termination — Verified entry points: `hooks.json:16-26`
- Surface #2 — Session termination — Verified entry points: `dispatch.py:49-54`
- Surface #2 — Session termination — Verified entry points: `acs_lib.py:1621`
- Surface #4 — Per-role model/effort — Verified entry points: `acs_lib.py:485-500`

## Entry-point anchor verification record

- Entry-point anchor verification record — PreToolUse matcher `Skill`, command `dispatch.py pre`, timeout 30: `hooks.json:3-14`
- Entry-point anchor verification record — SessionEnd hook, command `dispatch.py session-end`, timeout 30: `hooks.json:16-26`
- Entry-point anchor verification record — `def skill_name_from_payload(payload)`: `dispatch.py:25-38`
- Entry-point anchor verification record — `def main()` — routes by skill, exit 2 on missing/blocked: `dispatch.py:41-75`
- Entry-point anchor verification record — session-end branch → `acs_lib.session_end`: `dispatch.py:49-54`
- Entry-point anchor verification record — `HOOKED_SKILLS` allowlist: `acs_lib.py:43`
- Entry-point anchor verification record — `def resolve_role_model(settings, skill, role)`: `acs_lib.py:485-500`
- Entry-point anchor verification record — `def session_end(payload)`: `acs_lib.py:1621`
