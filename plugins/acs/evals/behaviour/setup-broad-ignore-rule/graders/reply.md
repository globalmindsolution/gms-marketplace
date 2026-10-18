---
type: llm
---

PASS if the final reply warns that the `.acs/` rule in .gitignore hides
`.acs/ci/check-conventions.py` (and `.acs/settings.json`) so CI cannot read
them, tells the user to add a `!.acs/` negation or narrow the rule
themselves, names the required check `Branch / PR / commit conventions`, and
lists the files to stage.
FAIL if it says the `.acs/` rule was changed or narrowed, claims setup itself
committed or force-added anything, says the check will work as is, or asks
the user a question. Not failures: reporting setup's own `.claude/worktrees/`
ignore entry, suggesting a narrower rule for the user to write, or telling
the user they can stage the script with `git add -f` -- the user acts there,
not setup.
