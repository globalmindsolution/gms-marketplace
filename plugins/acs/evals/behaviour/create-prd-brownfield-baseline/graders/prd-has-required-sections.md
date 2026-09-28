---
type: regex
target: { source: file, path: docs/product/prd.md }
pattern: '^#{1,3}\s+(?:\d+\.?\s+)?Vision\b[\s\S]*^#{1,3}\s+(?:\d+\.?\s+)?Problem statement[\s\S]*^#{1,3}\s+(?:\d+\.?\s+)?Target users (?:&|and) personas[\s\S]*^#{1,3}\s+(?:\d+\.?\s+)?Goals (?:&|and) success metrics[\s\S]*^#{1,3}\s+(?:\d+\.?\s+)?Features \(prioriti[sz]ed\)[\s\S]*^#{1,3}\s+(?:\d+\.?\s+)?Non-functional requirements[\s\S]*^#{1,3}\s+(?:\d+\.?\s+)?Constraints (?:&|and) assumptions[\s\S]*^#{1,3}\s+(?:\d+\.?\s+)?Out of scope'
flags: mi
---

The PRD sits at the conventional default (no PRD existed, so `<prd>` is
`docs/product/prd.md`) and carries EXACTLY the eight sections the author is
told to write, in order. The reviewer's structure floor checks the same list,
so a run that shipped without one skipped or overrode its own review.
