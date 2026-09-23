# Evidence sidecar — setup-state-root-setup.md

Companion `.evidence.md` file for
`docs/architecture/lld/flows/setup-state-root-setup.md`. Relocated
code-evidence citations, keyed by the body's own step identity ->
`[path:line]`.

- Retired-key detection + migration offer (Step 1): `plugins/acs/skills/setup/SKILL.md:42-46`, `plugins/acs/hooks/scripts/setup_wizard.py:210-223`
- State root resolution, no override (Step 3): `plugins/acs/hooks/scripts/setup_wizard.py:110-117`
- Tracked `.gitignore` retrofit (Step 3, layer 1): `plugins/acs/hooks/scripts/setup_wizard.py:392-397`
- Idempotent `info/exclude` append (Step 3, layer 2): `plugins/acs/hooks/scripts/setup_wizard.py:387-390`, `plugins/acs/hooks/scripts/setup_wizard.py:398-402`
- Combined `git check-ignore` re-check (Step 3): `plugins/acs/hooks/scripts/setup_wizard.py:404-407`
- Broad-`.acs/`-rule guard (Step 3): `plugins/acs/hooks/scripts/setup_wizard.py:408-411`
- State-root mkdir + writability check (Step 3): `plugins/acs/hooks/scripts/setup_wizard.py:485-507`
