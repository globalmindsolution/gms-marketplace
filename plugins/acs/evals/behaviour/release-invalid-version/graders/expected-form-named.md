---
type: regex
target: last_message
pattern: 'MAJOR\.MINOR\.PATCH|X\.Y\.Z|semver|semantic version|three-part|\d+\.\d+\.\d+'
flags: i
---

The error names the expected form (MAJOR.MINOR.PATCH, or an example such as
2.5.0 offered as a question rather than acted on). A bare "could not cut the
release" does not.
