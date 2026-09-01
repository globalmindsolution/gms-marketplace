# Evidence sidecar — initialize-state-root-setup.md

Companion `.evidence.md` file for
`docs/architecture/lld/flows/initialize-state-root-setup.md`. Relocated
code-evidence citations, keyed by the body's own step identity ->
`[path:line]`.

- Default-vs-override collection (Step 4): `plugins/acs/skills/initialize/SKILL.md:136-146`
- Tracked `.gitignore` retrofit (Step 5, layer 1): `plugins/acs/skills/initialize/SKILL.md:364-380`
- Idempotent `info/exclude` append (Step 5, layer 2): `plugins/acs/skills/initialize/SKILL.md:382-393`
- Combined `git check-ignore -v` assertion (Step 5): `plugins/acs/skills/initialize/SKILL.md:395-403`
- Broad-`.acs/`-rule guard (Step 5): `plugins/acs/skills/initialize/SKILL.md:405-415`
- State-root mkdir + write-probe (Step 6): `plugins/acs/skills/initialize/SKILL.md:419-447`
- Migrator invocation (Step 6b): `plugins/acs/skills/initialize/SKILL.md:453-470`
