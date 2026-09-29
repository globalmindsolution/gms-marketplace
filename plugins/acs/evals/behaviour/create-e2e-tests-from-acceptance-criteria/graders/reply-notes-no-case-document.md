---
type: regex
target: last_message
pattern: 'no (?:`?test-cases\.md`?|case document)|(?:`?test-cases\.md`?|case document) (?:was |is )?(?:absent|missing|not found|did not exist)|without (?:a )?(?:`?test-cases\.md`?|case document)|acceptance[- ]criteria fallback'
flags: i
---

"Say in the report that no case document existed."
