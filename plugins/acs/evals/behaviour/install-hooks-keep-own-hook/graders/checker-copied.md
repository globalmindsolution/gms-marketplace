---
type: file_exists
path: .acs/ci/check-conventions.py
---

Step 2 bootstraps .acs/ci/ from the plugin templates. Without the checker the
installed hooks exit 0 on every commit: installed, and checking nothing.
