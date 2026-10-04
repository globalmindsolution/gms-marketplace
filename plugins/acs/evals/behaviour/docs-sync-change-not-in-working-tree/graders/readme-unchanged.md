---
type: regex
target: { source: file, path: README.md }
pattern: 'lists customers, 20 per page by default\.\n$'
---

main's README is true of main's code (PAGE_SIZE 20). The change that raised it
lives on another branch, outside this working tree, so editing the README to
50 here -- committed or not -- documents code that is not there.
