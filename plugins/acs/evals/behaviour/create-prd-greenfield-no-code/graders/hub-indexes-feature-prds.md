---
type: regex
target: { source: file, path: docs/product/prd.md }
pattern: '^(?=[\s\S]*\]\(features/online-booking/prd\.md\))(?=[\s\S]*\]\(features/sms-reminders/prd\.md\))(?=[\s\S]*\]\(features/deposits/prd\.md\))(?=[\s\S]*\]\(features/loyalty-stamp-card/prd\.md\))'
---

The hub's Features (prioritized) section is the index: each committed feature
is a bullet linking its own PRD. The Won't-have marketplace may omit the link.
