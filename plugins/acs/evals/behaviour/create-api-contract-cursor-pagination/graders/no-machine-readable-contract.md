---
type: regex
target: files
pattern: '^docs/api/|(^|/)openapi[^/\n]*\.(ya?ml|json)$|\.proto$|(^|/)asyncapi[^/\n]*$'
flags: m
match: not_contains
---

Documents only (ADR-0134): the skill never writes a machine-readable contract
-- the repo keeps none and the prompt wants none. Were it to keep one,
/acs:create-impl-plan would plan its update from the approved contract and
/acs:code would write it.
