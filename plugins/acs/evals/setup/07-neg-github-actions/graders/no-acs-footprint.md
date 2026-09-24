---
type: regex
target: files
pattern: '(^|/)\.acs/(settings\.json|ci/)|acs-(conventions|tests|e2e)\.yml'
flags: m
match: not_contains
---

No acs configuration or acs CI file was created. The request was not about
acs, so setup's footprint anywhere in the files the run created is an
over-trigger with a visible cost: a settings file or workflow nobody asked for.
