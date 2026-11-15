---
description: >-
  Borrows the vocabulary of /acs:create-pr on purpose -- it is about
  pull requests and what they must contain -- while the request still belongs to this skill. It
  tests that the description, not a keyword, decides the route. Never names
  the skill.
expected_outcome: Routes to acs:setup.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Make sure nobody can merge a pull request that doesn't name its ticket — add the acs CI check for it.
