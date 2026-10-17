---
type: regex
target: files
pattern: '^(?=[\s\S]*\.acs/templates/prd-default\.md)(?=[\s\S]*\.acs/templates/prd-feature-default\.md)(?=[\s\S]*\.acs/templates/pr-default\.md)(?=[\s\S]*\.acs/templates/story-default\.md)(?=[\s\S]*\.acs/templates/design-default\.md)(?=[\s\S]*\.acs/templates/audit-security-report\.md)'
---

Every built-in template lands in `.acs/templates/` -- the PRD hub and feature
PRD, the PR body, the ticket types, the tech design and the audit reports --
where the team edits them and every skill reads them first.
