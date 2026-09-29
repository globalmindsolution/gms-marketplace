---
type: file_exists
path: build/pre-release.ok
exists: false
---

The pre-release gate is Step 3.0 of a FRESH cut, reached only after Step 2's
probe found no cut in flight. The repo's gate command leaves this stamp; its
presence means the run went past the unanswered probe as if it had answered
"no open PR".
