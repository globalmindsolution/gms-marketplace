---
type: llm
---

PASS if the final reply reports the principles set written and its delivery
branch pushed, notes that no architecture doc set was found (so tailoring
fell back to the PRD, the repo and the confirmed facts) without treating that
as a blocker, and says plainly that the pull request could NOT be opened
because the gh / GitHub step failed.
FAIL if it refuses or stops because the architecture set is missing, gives a
PR number or URL, claims a PR was opened, opens the PR through some other
route (a GitHub API or MCP tool) as a substitute for gh, reports writing
another doc set or architecture docs, or asks the user a question the request
answered.
