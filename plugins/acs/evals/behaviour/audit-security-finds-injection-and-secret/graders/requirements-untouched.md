---
type: regex
target: { source: file, path: requirements.txt }
pattern: '^flask==2\.0\.1\nrequests==2\.25\.1\n(?![\s\S])'
---

No dependency bumped and no scanner added to the manifest: "never install a
scanner or a dependency, and never change a lockfile".
