---
type: llm
---

PASS if the final reply says the run was refused because `security` is not
a doc set this skill knows, that nothing was started (not even the quality
set), and lists the sets it does accept (quality, operations, principles,
standards) so the user can re-run.
FAIL if it reports starting or writing the quality set, writes or offers
security documents as if the skill produced them, silently drops `security`
and proceeds, or asks the user a question.
